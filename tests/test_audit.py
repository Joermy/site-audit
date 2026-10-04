import json

import pytest

from site_audit import cli
from site_audit.audit import AuditResult, run_audit
from site_audit.fetch import CertInfo, Fetched
from site_audit.finding import Finding, Severity, Status
from site_audit.page import load_page, normalize_url
from site_audit.report import RENDERERS

from conftest import NOW, FakeNetwork, fixture_text

URL = "https://www.beispiel.test/"


def good_network():
    net = FakeNetwork()
    net.add(URL, body=fixture_text("gute-seite.html"), headers={"content-type": "text/html", "last-modified": "Mon, 15 Sep 2026 08:00:00 GMT"})
    net.add("https://www.beispiel.test/style.css", body="body{color:#222;background:#fff}h1{color:#111}img{max-width:100%;height:auto}", headers={"content-type": "text/css"})
    net.add("https://www.beispiel.test/bilder/werkstatt.jpg", body=b"x" * 40000)
    net.add("https://www.beispiel.test/bilder/holz.jpg", body=b"x" * 30000)
    net.add("https://www.beispiel.test/impressum/", body="Impressum")
    net.add("https://www.beispiel.test/datenschutz/", body="Datenschutz")
    net.add("http://www.beispiel.test/", final_url=URL, history=[("http://www.beispiel.test/", 301)])
    return net


def broken_network():
    net = FakeNetwork()
    net.add(URL, body=fixture_text("kaputte-seite.html"), headers={"content-type": "text/html", "server": "Apache/2.4.41"}, set_cookies=["PHPSESSID=abc; path=/"])
    net.add("http://www.beispiel.test/", body="x")
    return net


def problem_ids(result):
    return {f.check_id for f in result.problems}


def test_good_page_has_no_findings_in_the_documented_groups():
    result = run_audit(URL, good_network(), now=NOW)
    ignored = {"sec.headers"}
    assert problem_ids(result) - ignored == set(), [f.message for f in result.problems]


def test_broken_page_reproduces_the_hand_findings():
    result = run_audit(URL, broken_network(), now=NOW)
    ids = problem_ids(result)
    expected = {
        "legal.impressum",
        "legal.datenschutz",
        "meta.zoom",
        "a11y.alt",
        "a11y.lang",
        "a11y.headings",
        "a11y.contrast",
        "privacy.fonts",
        "privacy.tracker",
        "layout.overflow375",
        "content.stale",
        "seo.title",
        "sec.mixed",
        "sec.server",
        "sec.cookies",
        "tls.redirect",
    }
    assert expected <= ids, expected - ids
    assert result.worst() is Severity.HIGH


def test_findings_are_sorted_problems_first_by_severity():
    result = run_audit(URL, broken_network(), now=NOW)
    statuses = [f.status for f in result.findings]
    assert statuses == sorted(statuses, key=[Status.PROBLEM, Status.UNKNOWN, Status.OK].index)
    problem_ranks = [f.severity.rank for f in result.problems]
    assert problem_ranks == sorted(problem_ranks)


def test_every_finding_carries_a_message_and_a_title():
    result = run_audit(URL, broken_network(), now=NOW)
    assert all(f.message and f.title for f in result.findings)


def test_js_only_page_gets_a_warning():
    net = FakeNetwork()
    net.add(URL, body='<!doctype html><html lang="de"><head><title>App</title></head><body><div id="root"></div><script src="/app.js"></script></body></html>')
    page = load_page(URL, net, now=NOW)
    assert any("JavaScript" in w for w in page.warnings)


def test_normalize_url():
    assert normalize_url("beispiel.de") == "https://beispiel.de"
    assert normalize_url("http://beispiel.de/x") == "http://beispiel.de/x"
    with pytest.raises(ValueError):
        normalize_url("ftp://beispiel.de")


def test_unreachable_start_page_raises():
    net = FakeNetwork()
    net.responses[URL] = Fetched(url=URL, status=None, error="ConnectError: refused")
    with pytest.raises(ConnectionError):
        run_audit(URL, net, now=NOW)


@pytest.mark.parametrize("fmt", ["md", "html", "json"])
def test_reports_render_for_good_and_broken_pages(fmt):
    for net in (good_network(), broken_network()):
        result = run_audit(URL, net, now=NOW)
        text = RENDERERS[fmt](result)
        assert URL in text
        assert text.strip()


def test_json_report_is_valid_and_complete():
    result = run_audit(URL, broken_network(), now=NOW)
    data = json.loads(RENDERERS["json"](result))
    assert data["adresse"] == URL
    assert len(data["befunde"]) == len(result.findings)
    assert data["zusammenfassung"]["bestanden"] == len(result.passed)
    assert {"id", "title", "severity", "status", "message", "value", "where", "estimate"} <= set(data["befunde"][0])


def test_html_report_escapes_hostile_text():
    hostile = Finding("x.test", "<b>Titel</b>", Severity.HIGH, Status.PROBLEM, "<script>alert(1)</script>", value={"<k>": "<v>"}, where="<img src=x onerror=1>")
    result = AuditResult(requested_url="https://a.test", final_url="https://a.test", started_at=NOW, findings=[hostile], warnings=["<i>w</i>"])
    text = RENDERERS["html"](result)
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "<img src=x" not in text
    assert "<i>w</i>" not in text


def test_markdown_report_contains_sections_in_order():
    text = RENDERERS["md"](run_audit(URL, broken_network(), now=NOW))
    assert text.index("## Zusammenfassung") < text.index("## Befunde") < text.index("## Bestanden")
    assert "Schätzung" in text


def test_report_has_no_external_resources():
    text = RENDERERS["html"](run_audit(URL, good_network(), now=NOW))
    assert "<script" not in text and "<link" not in text
    assert "src=" not in text and "href=" not in text and "@import" not in text and "url(" not in text


class TestCli:
    def patch_network(self, monkeypatch, net):
        monkeypatch.setattr(cli, "make_network", lambda args: net)

    def test_list_checks(self, capsys):
        assert cli.main(["--liste"]) == 0
        output = capsys.readouterr().out
        assert "tls.cert" in output and "a11y.contrast" in output

    def test_missing_argument_is_an_error(self, capsys):
        assert cli.main([]) == cli.EXIT_ERROR

    def test_writes_json_report(self, monkeypatch, tmp_path):
        self.patch_network(monkeypatch, good_network())
        target = tmp_path / "bericht.json"
        assert cli.main([URL, "--format", "json", "--out", str(target)]) == 0
        assert json.loads(target.read_text(encoding="utf-8"))["adresse"] == URL

    def test_fail_on_threshold(self, monkeypatch, tmp_path):
        self.patch_network(monkeypatch, broken_network())
        target = tmp_path / "b.md"
        assert cli.main([URL, "--format", "md", "--out", str(target), "--fail-on", "hoch"]) == cli.EXIT_FINDINGS
        self.patch_network(monkeypatch, broken_network())
        assert cli.main([URL, "--format", "md", "--out", str(target), "--fail-on", "kritisch"]) == 0

    def test_robots_block_exits_with_code_3(self, monkeypatch, tmp_path):
        net = FakeNetwork()
        net.responses[URL] = Fetched(url=URL, status=None, blocked=True, error="durch robots.txt gesperrt")
        self.patch_network(monkeypatch, net)
        assert cli.main([URL, "--format", "md", "--out", str(tmp_path / "x.md")]) == cli.EXIT_ROBOTS

    def test_batch_writes_one_report_per_url(self, monkeypatch, tmp_path):
        net = good_network()
        self.patch_network(monkeypatch, net)
        urls = tmp_path / "urls.txt"
        urls.write_text("# Kommentar\nhttps://www.beispiel.test/\n\n", encoding="utf-8")
        out_dir = tmp_path / "berichte"
        assert cli.main(["--datei", str(urls), "--out-dir", str(out_dir), "--format", "html"]) == 0
        assert (out_dir / "www.beispiel.test.html").exists()

    def test_console_output(self, monkeypatch, capsys):
        self.patch_network(monkeypatch, broken_network())
        assert cli.main([URL]) == 0
        output = capsys.readouterr().out
        assert "Prüfbericht" in output and "legal.impressum" in output

    def test_only_filter(self, monkeypatch, tmp_path):
        self.patch_network(monkeypatch, broken_network())
        target = tmp_path / "b.json"
        cli.main([URL, "--format", "json", "--out", str(target), "--nur", "seo"])
        ids = {f["id"] for f in json.loads(target.read_text(encoding="utf-8"))["befunde"]}
        assert ids == {"seo.title", "seo.description"}
