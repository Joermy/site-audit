from __future__ import annotations

from urllib.parse import urlsplit

from . import check


@check("tls.reachable", title="HTTPS erreichbar", severity="kritisch")
def reachable(page, make):
    if page.scheme == "https":
        return make.ok("Die Seite wird über HTTPS ausgeliefert.", value=page.url)
    probe = page.net.head(f"https://{page.host}/")
    if probe.status is None:
        return make.problem("HTTPS ist nicht erreichbar.", value=probe.error, where=f"https://{page.host}/")
    return make.ok("HTTPS ist erreichbar.", value=probe.status, where=probe.url)


@check("tls.cert", title="Zertifikat gültig und Restlaufzeit", severity="kritisch")
def certificate(page, make):
    info = page.net.cert_info(page.host)
    if not info.reachable:
        return make.problem("Kein TLS-Verbindungsaufbau möglich.", value=info.error, where=f"{page.host}:443")
    if not info.valid:
        return make.problem("Das Zertifikat wird vom Browser nicht akzeptiert.", value=info.error, where=f"{page.host}:443")
    if info.not_after is None:
        return make.unknown("Ablaufdatum des Zertifikats nicht lesbar.")
    days = (info.not_after - page.now).days
    detail = {"tage": days, "bis": info.not_after.date().isoformat(), "aussteller": info.issuer, "tls": info.tls_version}
    if days < 0:
        return make.problem(f"Das Zertifikat ist seit {-days} Tagen abgelaufen.", value=detail, where=page.host)
    if days < 7:
        return make.problem(f"Das Zertifikat läuft in {days} Tagen ab.", value=detail, where=page.host, severity="hoch")
    if days < 14:
        return make.problem(f"Das Zertifikat läuft in {days} Tagen ab.", value=detail, where=page.host, severity="mittel")
    return make.ok(f"Zertifikat gültig, noch {days} Tage.", value=detail, where=page.host)


@check("tls.redirect", title="HTTP leitet auf HTTPS um", severity="hoch")
def redirect(page, make):
    start = f"http://{page.host}/"
    result = page.net.head(start)
    if result.status is None:
        return make.ok("HTTP ist nicht erreichbar, die Seite ist nur über HTTPS offen.", value=result.error, where=start)
    chain = [f"{status} {url}" for url, status in result.history] + [f"{result.status} {result.url}"]
    final_https = urlsplit(result.url).scheme == "https"
    if not final_https:
        return make.problem("HTTP bleibt ohne Weiterleitung erreichbar.", value=chain, where=start)
    first_status = result.history[0][1] if result.history else None
    if first_status in (302, 303, 307):
        return make.problem(
            "Die Weiterleitung auf HTTPS ist nur vorläufig (kein 301 oder 308).",
            value=chain,
            where=start,
            severity="hinweis",
        )
    return make.ok("HTTP leitet dauerhaft auf HTTPS um.", value=chain, where=start)
