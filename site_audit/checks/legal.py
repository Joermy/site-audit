from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlsplit

from . import check

IMPRINT = re.compile(r"impressum|anbieterkennzeichnung|imprint|legal[\s-]?notice", re.I)
PRIVACY = re.compile(r"datenschutz|privacy|data[\s-]?protection", re.I)


def find_link(page, pattern: re.Pattern) -> str | None:
    best: str | None = None
    for anchor in page.soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        text = anchor.get_text(" ", strip=True)
        path = urlsplit(href).path
        if pattern.search(text) or pattern.search(path):
            url = urldefrag(urljoin(page.url, href))[0]
            if best is None or (page.is_first_party(url) and not page.is_first_party(best)):
                best = url
    return best


def _check_page(page, make, pattern: re.Pattern, name: str, dative: str):
    link = find_link(page, pattern)
    if link is None:
        return make.problem(
            f"Auf der Startseite ist kein Link {dative} gefunden worden.",
            value=None,
            where=page.url,
        )
    fetched = page.net.get(link)
    if fetched.status is None:
        return make.problem(f"{name} ist verlinkt, aber nicht erreichbar.", value=fetched.error, where=link)
    if not fetched.ok:
        return make.problem(f"{name} ist verlinkt, die Seite antwortet mit Status {fetched.status}.", value=fetched.status, where=link)
    return make.ok(f"{name} ist verlinkt und erreichbar.", value={"url": link, "status": fetched.status}, where=link)


@check("legal.impressum", title="Impressum verlinkt und erreichbar", severity="hoch")
def imprint(page, make):
    return _check_page(page, make, IMPRINT, "Impressum", "zum Impressum")


@check("legal.datenschutz", title="Datenschutzerklärung verlinkt und erreichbar", severity="hoch")
def privacy_notice(page, make):
    return _check_page(page, make, PRIVACY, "Datenschutzerklärung", "zur Datenschutzerklärung")
