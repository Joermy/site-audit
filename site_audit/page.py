from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urldefrag

from bs4 import BeautifulSoup

from .css import Stylesheet, extract_urls, parse_css
from .fetch import Fetched, Network, RobotsBlocked

FONT_EXTENSIONS = (".woff2", ".woff", ".ttf", ".otf", ".eot")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico", ".bmp")
SCRIPT_EXTENSIONS = (".js", ".mjs")
CSS_EXTENSIONS = (".css",)


@dataclass
class Resource:
    url: str
    kind: str
    tag: str
    external: bool
    integrity: bool = False
    size: int | None = None
    status: int | None = None


@dataclass
class Page:
    requested_url: str
    url: str
    status: int | None
    headers: dict[str, str]
    set_cookies: list[str]
    html: str
    soup: BeautifulSoup
    html_bytes: int
    net: Network
    redirect_chain: list[tuple[str, int]] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    stylesheets: list[tuple[str, Stylesheet]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def host(self) -> str:
        return (urlsplit(self.url).hostname or "").lower()

    @property
    def scheme(self) -> str:
        return urlsplit(self.url).scheme

    def is_first_party(self, url: str) -> bool:
        return same_party(urlsplit(url).hostname or "", self.host)

    def all_rules(self):
        for _, sheet in self.stylesheets:
            for rule in sheet.rules:
                yield rule


def same_party(host_a: str, host_b: str) -> bool:
    a = host_a.lower().removeprefix("www.")
    b = host_b.lower().removeprefix("www.")
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        raw = "https://" + raw
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"keine gültige Webadresse: {raw}")
    return raw


def classify(tag: str, url: str, rel: str = "", as_attr: str = "") -> str:
    path = urlsplit(url).path.lower()
    if tag == "link" and "stylesheet" in rel:
        return "css"
    if tag == "script":
        return "js"
    if tag == "link" and "preload" in rel:
        return {"font": "font", "style": "css", "script": "js", "image": "img"}.get(as_attr, "other")
    if tag in ("img", "source") and not path.endswith((".mp4", ".webm", ".ogg")):
        return "img"
    if tag == "link" and ("icon" in rel or "apple-touch" in rel):
        return "img"
    if tag == "iframe":
        return "frame"
    if tag in ("video", "audio", "source"):
        return "media"
    if path.endswith(FONT_EXTENSIONS):
        return "font"
    if path.endswith(IMAGE_EXTENSIONS):
        return "img"
    if path.endswith(CSS_EXTENSIONS):
        return "css"
    if path.endswith(SCRIPT_EXTENSIONS):
        return "js"
    return "other"


def first_srcset_url(value: str) -> str | None:
    for candidate in value.split(","):
        candidate = candidate.strip()
        if candidate:
            return candidate.split()[0]
    return None


def discover_resources(page: Page) -> None:
    seen: set[str] = set()

    def add(raw: str | None, tag: str, rel: str = "", as_attr: str = "", integrity: bool = False) -> None:
        if not raw:
            return
        raw = raw.strip()
        if raw.startswith(("data:", "javascript:", "mailto:", "tel:", "#", "blob:")):
            return
        absolute = urldefrag(urljoin(page.url, raw))[0]
        if urlsplit(absolute).scheme not in ("http", "https") or absolute in seen:
            return
        seen.add(absolute)
        page.resources.append(
            Resource(
                url=absolute,
                kind=classify(tag, absolute, rel, as_attr),
                tag=tag,
                external=not page.is_first_party(absolute),
                integrity=integrity,
            )
        )

    soup = page.soup
    for node in soup.find_all("link", href=True):
        rel = " ".join(node.get("rel", [])).lower()
        if any(word in rel for word in ("stylesheet", "preload", "icon", "apple-touch", "modulepreload", "prefetch")):
            add(node["href"], "link", rel, (node.get("as") or "").lower(), bool(node.get("integrity")))
    for node in soup.find_all("script", src=True):
        add(node["src"], "script", integrity=bool(node.get("integrity")))
    for node in soup.find_all(["img", "source"]):
        add(node.get("src") or first_srcset_url(node.get("srcset") or ""), node.name)
    for node in soup.find_all(["iframe", "video", "audio", "embed"]):
        add(node.get("src"), node.name)
    for node in soup.find_all(style=True):
        for url in extract_urls(node["style"]):
            add(url, "style")
    for node in soup.find_all("style"):
        sheet_text = node.get_text()
        page.stylesheets.append((page.url, parse_css(sheet_text)))
        for url in extract_urls(sheet_text):
            add(url, "style")


def measure_resources(page: Page, max_resources: int) -> None:
    first_party = [r for r in page.resources if not r.external]
    if len(first_party) > max_resources:
        page.warnings.append(
            f"{len(first_party)} eigene Ressourcen gefunden, nur die ersten {max_resources} wurden gemessen. "
            "Gewicht und Anfragezahl sind deshalb untere Grenzen."
        )
    queue = first_party[:max_resources]
    processed = 0
    while processed < len(queue):
        resource = queue[processed]
        processed += 1
        if resource.kind == "css":
            fetched = page.net.get(resource.url)
            resource.status = fetched.status
            resource.size = fetched.transfer_size if fetched.transfer_size is not None else len(fetched.body)
            if fetched.ok:
                sheet = parse_css(fetched.text)
                page.stylesheets.append((resource.url, sheet))
                for raw in sheet.imports + extract_urls(fetched.text):
                    absolute = urldefrag(urljoin(resource.url, raw))[0]
                    if urlsplit(absolute).scheme not in ("http", "https"):
                        continue
                    if any(r.url == absolute for r in page.resources):
                        continue
                    child = Resource(
                        url=absolute,
                        kind=classify("style", absolute),
                        tag="css-url",
                        external=not page.is_first_party(absolute),
                    )
                    page.resources.append(child)
                    if not child.external and len(queue) < max_resources:
                        queue.append(child)
            continue
        fetched = page.net.head(resource.url)
        resource.status = fetched.status
        if fetched.transfer_size is not None:
            resource.size = fetched.transfer_size
        elif fetched.body:
            resource.size = len(fetched.body)
        elif fetched.status and fetched.status < 400:
            full = page.net.get(resource.url)
            resource.size = len(full.body)


def visible_text_length(soup: BeautifulSoup) -> int:
    clone = BeautifulSoup(str(soup), "lxml")
    for node in clone(["script", "style", "noscript", "template"]):
        node.decompose()
    return len(re.sub(r"\s+", " ", clone.get_text(" ", strip=True)))


def build_page(fetched: Fetched, requested_url: str, net: Network, now: datetime | None = None) -> Page:
    html = fetched.text
    soup = BeautifulSoup(html, "lxml")
    page = Page(
        requested_url=requested_url,
        url=fetched.url,
        status=fetched.status,
        headers=fetched.headers,
        set_cookies=fetched.set_cookies,
        html=html,
        soup=soup,
        html_bytes=fetched.transfer_size if fetched.transfer_size is not None else len(fetched.body),
        net=net,
        redirect_chain=list(fetched.history),
        now=now or datetime.now(timezone.utc),
    )
    if fetched.truncated:
        page.warnings.append("Die Startseite war größer als die Lesegrenze und wurde abgeschnitten.")
    discover_resources(page)
    if visible_text_length(soup) < 200 and soup.find("script"):
        page.warnings.append(
            "Der sichtbare Text der Startseite ist sehr kurz, die Seite baut ihren Inhalt vermutlich per JavaScript auf. "
            "Dieses Werkzeug führt kein JavaScript aus; mehrere Ergebnisse können unvollständig sein."
        )
    return page


def load_page(url: str, net: Network, *, max_resources: int = 60, now: datetime | None = None) -> Page:
    url = normalize_url(url)
    fetched = net.get(url)
    if fetched.blocked:
        raise RobotsBlocked(url)
    if fetched.status is None:
        raise ConnectionError(fetched.error or "Seite nicht erreichbar")
    page = build_page(fetched, url, net, now)
    measure_resources(page, max_resources)
    return page
