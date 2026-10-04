from __future__ import annotations

import re

from . import check

VERSIONED_SERVER = re.compile(r"[A-Za-z][\w.-]*/\d")
SESSION_NAME = re.compile(r"sess|token|auth|login|sid|jwt", re.I)


@check("sec.headers", title="Sicherheits-Header", severity="mittel")
def headers(page, make):
    present = page.headers
    csp = present.get("content-security-policy", "")
    missing: list[str] = []
    if page.scheme == "https" and "strict-transport-security" not in present:
        missing.append("Strict-Transport-Security")
    if not csp:
        missing.append("Content-Security-Policy")
    if present.get("x-content-type-options", "").lower() != "nosniff":
        missing.append("X-Content-Type-Options: nosniff")
    if "x-frame-options" not in present and "frame-ancestors" not in csp:
        missing.append("X-Frame-Options oder frame-ancestors")
    if "referrer-policy" not in present:
        missing.append("Referrer-Policy")
    if "permissions-policy" not in present:
        missing.append("Permissions-Policy")
    value = {"fehlend": missing, "vorhanden": sorted(k for k in present if k in SECURITY_HEADERS)}
    if not missing:
        return make.ok("Alle geprüften Sicherheits-Header sind gesetzt.", value=value)
    critical = {"Strict-Transport-Security", "Content-Security-Policy"} & set(missing)
    return make.problem(
        f"{len(missing)} von 6 Sicherheits-Headern fehlen: {', '.join(missing)}.",
        value=value,
        severity="mittel" if critical else "hinweis",
    )


SECURITY_HEADERS = {
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
}


def _parse_cookie(raw: str) -> tuple[str, set[str], dict[str, str]]:
    parts = [p.strip() for p in raw.split(";")]
    name = parts[0].split("=", 1)[0]
    flags = {p.lower() for p in parts[1:] if "=" not in p}
    attributes = {k.lower(): v for k, _, v in (p.partition("=") for p in parts[1:] if "=" in p)}
    return name, flags, attributes


@check("sec.cookies", title="Cookie-Eigenschaften", severity="mittel")
def cookies(page, make):
    if not page.set_cookies:
        return make.ok("Die Startseite setzt keine Cookies.", value=[])
    issues: list[str] = []
    for raw in page.set_cookies:
        name, flags, attributes = _parse_cookie(raw)
        if page.scheme == "https" and "secure" not in flags:
            issues.append(f"{name}: ohne Secure")
        if "httponly" not in flags and SESSION_NAME.search(name):
            issues.append(f"{name}: ohne HttpOnly")
        if "samesite" not in attributes:
            issues.append(f"{name}: ohne SameSite")
    names = [_parse_cookie(c)[0] for c in page.set_cookies]
    if issues:
        return make.problem(f"{len(issues)} Auffälligkeiten bei {len(names)} Cookies.", value={"cookies": names, "auffaellig": issues})
    return make.ok(f"{len(names)} Cookies mit Secure, HttpOnly und SameSite.", value=names)


@check("sec.mixed", title="Unverschlüsselte Inhalte auf HTTPS-Seite", severity="hoch")
def mixed(page, make):
    if page.scheme != "https":
        return make.unknown("Die Seite wird nicht über HTTPS ausgeliefert, die Prüfung entfällt.")
    insecure = [r for r in page.resources if r.url.startswith("http://")]
    if not insecure:
        return make.ok("Alle Ressourcen werden über HTTPS geladen.")
    active = [r.url for r in insecure if r.kind in ("js", "css", "frame")]
    value = {"aktiv": active, "passiv": [r.url for r in insecure if r.url not in active]}
    return make.problem(
        f"{len(insecure)} Ressourcen werden über unverschlüsseltes HTTP geladen.",
        value=value,
        severity="hoch" if active else "mittel",
    )


@check("sec.server", title="Versionsangabe im Server-Header", severity="hinweis")
def server(page, make):
    exposed = {k: v for k, v in page.headers.items() if k in ("server", "x-powered-by", "x-aspnet-version") and VERSIONED_SERVER.search(v)}
    if exposed:
        return make.problem("Der Server nennt Software und Version.", value=exposed)
    return make.ok("Keine Versionsangabe im Server-Header.")


@check("sec.sri", title="Fremde Skripte und Stile mit Integritätsprüfung", severity="hinweis")
def subresource_integrity(page, make):
    unprotected = [r.url for r in page.resources if r.external and r.kind in ("js", "css") and not r.integrity]
    if unprotected:
        return make.problem(
            f"{len(unprotected)} fremde Skripte oder Stile ohne integrity-Attribut.",
            value=unprotected[:8],
        )
    return make.ok("Keine fremden Skripte oder Stile ohne integrity-Attribut.")
