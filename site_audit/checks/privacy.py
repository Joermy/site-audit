from __future__ import annotations

from collections import Counter
from urllib.parse import urlsplit

from . import check

GOOGLE_FONT_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}
OTHER_FONT_HOSTS = {"use.typekit.net", "p.typekit.net", "fast.fonts.net", "fonts.bunny.net", "use.fontawesome.com", "kit.fontawesome.com"}
TRACKER_MARKERS = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "googlesyndication.com",
    "connect.facebook.net",
    "facebook.com/tr",
    "hotjar.com",
    "clarity.ms",
    "static.cloudflareinsights.com",
    "analytics.tiktok.com",
    "snap.licdn.com",
    "bat.bing.com",
)


def _external(page):
    return [r for r in page.resources if r.external]


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


@check("privacy.external", title="Ressourcen von fremden Domains", severity="mittel")
def external(page, make):
    hosts = Counter(_host(r.url) for r in _external(page))
    if not hosts:
        return make.ok("Die Seite lädt nichts von fremden Domains.", value={})
    total = sum(hosts.values())
    return make.problem(
        f"{total} Anfragen an {len(hosts)} fremde Domains. Beim Laden erfährt jede dieser Domains die IP-Adresse des Besuchers.",
        value=dict(hosts.most_common()),
    )


@check("privacy.fonts", title="Schriften von Google oder einem anderen Dienst geladen", severity="hoch")
def fonts(page, make):
    google = sorted({_host(r.url) for r in _external(page) if _host(r.url) in GOOGLE_FONT_HOSTS})
    if google:
        return make.problem(
            "Schriften werden von Google-Servern geladen. Lokal ausgelieferte Schriften vermeiden die Übertragung der IP-Adresse.",
            value=google,
        )
    others = sorted({_host(r.url) for r in _external(page) if _host(r.url) in OTHER_FONT_HOSTS})
    if others:
        return make.problem(
            "Schriften werden von einem fremden Dienst geladen.",
            value=others,
            severity="mittel",
        )
    return make.ok("Keine Schriften von fremden Diensten gefunden.")


@check("privacy.tracker", title="Dienste zur Reichweitenmessung oder Werbung", severity="mittel")
def trackers(page, make):
    found = sorted({r.url.split("?")[0] for r in _external(page) if any(marker in r.url for marker in TRACKER_MARKERS)})
    if found:
        return make.problem("Es werden Dienste zur Reichweitenmessung oder Werbung geladen.", value=found)
    return make.ok("Keine bekannten Mess- oder Werbedienste gefunden.")
