from datetime import timedelta

import pytest

from site_audit.checks import REGISTRY, run_checks
from site_audit.fetch import CertInfo
from site_audit.finding import Severity, Status

from conftest import NOW, FakeNetwork, make_page


def run(page, check_id):
    findings = run_checks(page, only=[check_id])
    assert len(findings) == 1, findings
    return findings[0]


HEAD_OPEN = '<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Eine Testseite für Prüfungen</title>{head}</head><body>{body}</body></html>'


def doc(body="<h1>Titel</h1><p>Text</p>", head=""):
    return HEAD_OPEN.format(head=head, body=body)


def test_registry_contains_every_documented_check():
    expected = {
        "tls.reachable", "tls.cert", "tls.redirect",
        "meta.viewport", "meta.zoom", "layout.overflow375",
        "legal.impressum", "legal.datenschutz",
        "privacy.external", "privacy.fonts", "privacy.tracker",
        "a11y.alt", "a11y.lang", "a11y.headings", "a11y.contrast",
        "perf.weight", "perf.requests",
        "content.stale", "seo.title", "seo.description",
        "sec.headers", "sec.cookies", "sec.mixed", "sec.server", "sec.sri",
    }
    assert expected <= set(REGISTRY)


def test_a_crashing_check_becomes_unknown_instead_of_aborting(monkeypatch):
    spec = REGISTRY["seo.title"]

    def boom(page, make):
        raise RuntimeError("kaputt")

    monkeypatch.setitem(REGISTRY, "seo.title", type(spec)(spec.check_id, spec.title, spec.severity, boom))
    finding = run(make_page(doc()), "seo.title")
    assert finding.status is Status.UNKNOWN
    assert "kaputt" in finding.message


class TestMeta:
    def test_viewport_missing(self):
        finding = run(make_page(doc()), "meta.viewport")
        assert finding.is_problem and finding.severity is Severity.HIGH

    def test_viewport_ok(self):
        head = '<meta name="viewport" content="width=device-width, initial-scale=1">'
        assert run(make_page(doc(head=head)), "meta.viewport").status is Status.OK

    @pytest.mark.parametrize(
        "content,blocked",
        [
            ("width=device-width, initial-scale=1, maximum-scale=1", True),
            ("width=device-width, user-scalable=no", True),
            ("width=device-width, maximum-scale=5", False),
            ("width=device-width, initial-scale=1", False),
        ],
    )
    def test_zoom(self, content, blocked):
        page = make_page(doc(head=f'<meta name="viewport" content="{content}">'))
        assert run(page, "meta.zoom").is_problem is blocked

    def test_overflow_flags_fixed_widths_as_estimate(self):
        body = '<table width="800"><tr><td>x</td></tr></table><div style="width:600px">y</div>'
        head = "<style>.a{min-width:500px}.b{width:300px}@media (min-width:900px){.c{width:1000px}}</style>"
        finding = run(make_page(doc(body, head)), "layout.overflow375")
        assert finding.is_problem and finding.estimate
        assert finding.value["anzahl"] == 3

    def test_overflow_ignores_absolutely_positioned_decoration(self):
        head = "<style>.glow{position:absolute;width:560px;height:560px}</style>"
        assert run(make_page(doc(head=head)), "layout.overflow375").status is Status.OK

    def test_overflow_ignores_decoration_positioned_by_a_more_general_rule(self):
        head = "<style>.stage span{position:absolute}.stage span:nth-child(1){width:560px}</style>"
        assert run(make_page(doc(head=head)), "layout.overflow375").status is Status.OK

    def test_overflow_ignores_desktop_only_media_rules(self):
        head = "<style>@media (min-width:900px){.c{width:1000px}}</style>"
        finding = run(make_page(doc(head=head)), "layout.overflow375")
        assert finding.status is Status.OK and finding.estimate


class TestA11y:
    def test_alt_missing(self):
        page = make_page(doc('<h1>T</h1><img src="a.jpg"><img src="b.jpg" alt=""><img src="c.jpg" alt="Foto">'))
        finding = run(page, "a11y.alt")
        assert finding.is_problem and finding.value == {"ohne_alt": 1, "gesamt": 3}

    def test_alt_all_present(self):
        assert run(make_page(doc('<h1>T</h1><img src="a.jpg" alt="x">')), "a11y.alt").status is Status.OK

    def test_lang(self):
        assert run(make_page("<html><head><title>x</title></head><body><h1>a</h1></body></html>"), "a11y.lang").is_problem
        assert run(make_page(doc()), "a11y.lang").status is Status.OK

    def test_headings_skip_and_missing_h1(self):
        finding = run(make_page(doc("<h2>A</h2><h4>B</h4>")), "a11y.headings")
        assert finding.is_problem and finding.severity is Severity.MEDIUM
        assert any("h2 auf h4" in p for p in finding.value)

    def test_headings_ok(self):
        assert run(make_page(doc("<h1>A</h1><h2>B</h2><h3>C</h3>")), "a11y.headings").status is Status.OK

    def test_contrast_flags_light_gray_text(self):
        head = "<style>body{color:#999;background:#fff}</style>"
        finding = run(make_page(doc(head=head)), "a11y.contrast")
        assert finding.is_problem
        assert finding.value["niedrigster"] == pytest.approx(2.85, abs=0.01)
        assert finding.severity is Severity.HIGH

    def test_contrast_good_colors(self):
        head = "<style>body{color:#222;background:#fff}</style>"
        assert run(make_page(doc(head=head)), "a11y.contrast").status is Status.OK

    def test_contrast_resolves_custom_properties(self):
        head = "<style>:root{--t:#777;--b:#fff}body{color:var(--t);background:var(--b)}</style>"
        finding = run(make_page(doc(head=head)), "a11y.contrast")
        assert finding.is_problem and finding.value["niedrigster"] == pytest.approx(4.48, abs=0.01)

    def test_contrast_unknown_without_css(self):
        assert run(make_page(doc()), "a11y.contrast").status is Status.UNKNOWN

    def test_contrast_ignores_rules_with_only_one_side(self):
        head = "<style>body{color:#222;background:#fff}.papier{background:#fbf9f5}.dunkel p{color:#eee}</style>"
        finding = run(make_page(doc(head=head)), "a11y.contrast")
        assert finding.status is Status.OK and finding.value["gemessen"] == 1

    def test_contrast_measures_complete_pairs_in_one_rule(self):
        head = "<style>body{color:#222;background:#fff}.karte{color:#aaa;background:#fff}</style>"
        finding = run(make_page(doc(head=head)), "a11y.contrast")
        assert finding.is_problem and finding.where == ".karte"


class TestPrivacy:
    def test_google_fonts_is_high(self):
        head = '<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=X">'
        finding = run(make_page(doc(head=head)), "privacy.fonts")
        assert finding.is_problem and finding.severity is Severity.HIGH

    def test_external_grouped_by_host(self):
        head = '<script src="https://cdn.example.org/a.js"></script><script src="https://cdn.example.org/b.js"></script><link rel="stylesheet" href="https://other.example.net/x.css">'
        finding = run(make_page(doc(head=head)), "privacy.external")
        assert finding.value == {"cdn.example.org": 2, "other.example.net": 1}

    def test_subdomain_counts_as_first_party(self):
        head = '<link rel="stylesheet" href="https://static.beispiel.test/x.css">'
        assert run(make_page(doc(head=head)), "privacy.external").status is Status.OK

    def test_tracker(self):
        head = '<script src="https://www.googletagmanager.com/gtag/js?id=G-1"></script>'
        assert run(make_page(doc(head=head)), "privacy.tracker").is_problem


class TestLegal:
    def make_net(self, imprint=200, privacy=200):
        net = FakeNetwork()
        net.add("https://www.beispiel.test/impressum/", status=imprint)
        net.add("https://www.beispiel.test/datenschutz/", status=privacy)
        return net

    BODY = '<h1>T</h1><a href="/impressum/">Impressum</a> <a href="/datenschutz/">Datenschutzerklärung</a>'

    def test_both_present(self):
        page = make_page(doc(self.BODY), net=self.make_net())
        assert run(page, "legal.impressum").status is Status.OK
        assert run(page, "legal.datenschutz").status is Status.OK

    def test_link_missing(self):
        page = make_page(doc("<h1>T</h1><a href='/kontakt/'>Kontakt</a>"))
        assert run(page, "legal.impressum").is_problem
        assert run(page, "legal.datenschutz").is_problem

    def test_link_present_but_page_404(self):
        page = make_page(doc(self.BODY), net=self.make_net(imprint=404))
        finding = run(page, "legal.impressum")
        assert finding.is_problem and finding.value == 404

    def test_link_found_by_path_not_text(self):
        net = self.make_net()
        page = make_page(doc("<h1>T</h1><a href='/impressum/'>Rechtliches</a>"), net=net)
        assert run(page, "legal.impressum").status is Status.OK


class TestPerfContentSeo:
    def test_weight_sums_first_party_only(self):
        net = FakeNetwork()
        net.add("https://www.beispiel.test/s.css", body="a" * 2000, headers={"content-type": "text/css"})
        net.add("https://www.beispiel.test/p.jpg", body=b"x" * 5000)
        head = '<link rel="stylesheet" href="/s.css"><link rel="stylesheet" href="https://fremd.test/x.css">'
        page = make_page(doc('<h1>T</h1><img src="/p.jpg" alt="x">', head), net=net, measure=True)
        finding = run(page, "perf.weight")
        assert finding.value["css"] == 2000
        assert finding.value["img"] == 5000
        assert finding.value["gesamt"] == finding.value["html"] + 7000

    def test_weight_limit(self):
        net = FakeNetwork()
        net.add("https://www.beispiel.test/big.jpg", body=b"x" * (2 * 1024 * 1024))
        page = make_page(doc('<h1>T</h1><img src="/big.jpg" alt="x">'), net=net, measure=True)
        finding = run(page, "perf.weight")
        assert finding.is_problem and finding.severity is Severity.MEDIUM

    def test_requests_counted(self):
        imgs = "".join(f'<img src="/i{n}.jpg" alt="x">' for n in range(60))
        finding = run(make_page(doc(imgs)), "perf.requests")
        assert finding.is_problem and finding.value["gesamt"] == 61

    def test_stale_copyright(self):
        old = run(make_page(doc("<h1>T</h1><p>© 2019 Firma</p>")), "content.stale")
        assert old.is_problem and old.severity is Severity.MEDIUM
        current = run(make_page(doc("<h1>T</h1><p>© 2024–2026 Firma</p>")), "content.stale")
        assert current.status is Status.OK

    def test_stale_uses_last_modified_header(self):
        page = make_page(doc(), headers={"Last-Modified": "Tue, 01 Jul 2025 10:00:00 GMT"})
        assert run(page, "content.stale").status is Status.OK

    def test_stale_unknown_without_signals(self):
        assert run(make_page(doc()), "content.stale").status is Status.UNKNOWN

    def test_title(self):
        assert run(make_page("<html><head></head><body></body></html>"), "seo.title").is_problem
        assert run(make_page(doc()), "seo.title").status is Status.OK

    def test_description(self):
        head = '<meta name="description" content="Kurz">'
        assert run(make_page(doc(head=head)), "seo.description").is_problem


class TestTls:
    def test_https_page_is_reachable(self):
        assert run(make_page(doc()), "tls.reachable").status is Status.OK

    def test_http_page_without_working_https(self):
        net = FakeNetwork()
        net.add("https://www.beispiel.test/", status=200)
        net.responses["https://www.beispiel.test/"].status = None
        net.responses["https://www.beispiel.test/"].error = "ConnectError: refused"
        page = make_page(doc(), url="http://www.beispiel.test/", net=net)
        finding = run(page, "tls.reachable")
        assert finding.is_problem and finding.severity is Severity.CRITICAL
        assert "ConnectError" in finding.value

    @pytest.mark.parametrize("days,severity", [(5, Severity.HIGH), (10, Severity.MEDIUM)])
    def test_cert_days_left(self, days, severity):
        net = FakeNetwork(cert=CertInfo(reachable=True, valid=True, not_after=NOW + timedelta(days=days), issuer="X"))
        finding = run(make_page(doc(), net=net), "tls.cert")
        assert finding.is_problem and finding.severity is severity and finding.value["tage"] == days

    def test_cert_with_three_weeks_left_is_fine(self):
        net = FakeNetwork(cert=CertInfo(reachable=True, valid=True, not_after=NOW + timedelta(days=21), issuer="X"))
        assert run(make_page(doc(), net=net), "tls.cert").status is Status.OK

    def test_cert_expired(self):
        net = FakeNetwork(cert=CertInfo(reachable=True, valid=True, not_after=NOW - timedelta(days=3)))
        finding = run(make_page(doc(), net=net), "tls.cert")
        assert finding.is_problem and finding.severity is Severity.CRITICAL

    def test_cert_invalid_keeps_error_text(self):
        net = FakeNetwork(cert=CertInfo(reachable=True, valid=False, error="certificate has expired"))
        finding = run(make_page(doc(), net=net), "tls.cert")
        assert finding.is_problem and finding.value == "certificate has expired"

    def test_cert_ok(self):
        assert run(make_page(doc()), "tls.cert").status is Status.OK

    def test_redirect_permanent_ok(self):
        net = FakeNetwork()
        net.add("http://www.beispiel.test/", status=200, final_url="https://www.beispiel.test/", history=[("http://www.beispiel.test/", 301)])
        finding = run(make_page(doc(), net=net), "tls.redirect")
        assert finding.status is Status.OK and finding.value[0].startswith("301")

    def test_redirect_temporary_is_note(self):
        net = FakeNetwork()
        net.add("http://www.beispiel.test/", status=200, final_url="https://www.beispiel.test/", history=[("http://www.beispiel.test/", 302)])
        finding = run(make_page(doc(), net=net), "tls.redirect")
        assert finding.is_problem and finding.severity is Severity.NOTE

    def test_no_redirect_is_high(self):
        net = FakeNetwork()
        net.add("http://www.beispiel.test/", status=200)
        finding = run(make_page(doc(), net=net), "tls.redirect")
        assert finding.is_problem and finding.severity is Severity.HIGH

    def test_http_closed_is_fine(self):
        net = FakeNetwork()
        net.add("http://www.beispiel.test/", status=200)
        net.responses["http://www.beispiel.test/"].status = None
        net.responses["http://www.beispiel.test/"].error = "ConnectError"
        assert run(make_page(doc(), net=net), "tls.redirect").status is Status.OK


class TestSecurity:
    def test_missing_headers(self):
        finding = run(make_page(doc()), "sec.headers")
        assert finding.is_problem and len(finding.value["fehlend"]) == 6

    def test_all_headers(self):
        headers = {
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=()",
        }
        assert run(make_page(doc(), headers=headers), "sec.headers").status is Status.OK

    def test_cookies(self):
        page = make_page(doc(), cookies=["sessionid=abc; Path=/", "ok=1; Secure; HttpOnly; SameSite=Lax"])
        finding = run(page, "sec.cookies")
        assert finding.is_problem
        assert "sessionid: ohne Secure" in finding.value["auffaellig"]
        assert "sessionid: ohne HttpOnly" in finding.value["auffaellig"]

    def test_no_cookies_is_ok(self):
        assert run(make_page(doc()), "sec.cookies").status is Status.OK

    def test_mixed_content(self):
        head = '<script src="http://www.beispiel.test/a.js"></script><link rel="icon" href="http://www.beispiel.test/f.ico">'
        finding = run(make_page(doc(head=head)), "sec.mixed")
        assert finding.is_problem and finding.severity is Severity.HIGH
        assert finding.value["aktiv"] == ["http://www.beispiel.test/a.js"]

    def test_server_header_version(self):
        page = make_page(doc(), headers={"Server": "Apache/2.4.41", "X-Powered-By": "PHP"})
        finding = run(page, "sec.server")
        assert finding.is_problem and list(finding.value) == ["server"]

    def test_subresource_integrity(self):
        head = '<script src="https://cdn.example.org/a.js"></script><script src="https://cdn.example.org/b.js" integrity="sha384-x" crossorigin></script>'
        finding = run(make_page(doc(head=head)), "sec.sri")
        assert finding.is_problem and finding.value == ["https://cdn.example.org/a.js"]
