from __future__ import annotations

import re

from ..css import parse_declarations
from . import check

VIEWPORT_WIDTH = 375


def _viewport_content(page) -> str | None:
    tag = page.soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    if tag and tag.get("content"):
        return tag["content"]
    return None


def _parse_viewport(content: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in re.split(r"[,;]", content):
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip().lower()] = value.strip().lower()
    return result


@check("meta.viewport", title="viewport-Angabe vorhanden", severity="hoch")
def viewport(page, make):
    content = _viewport_content(page)
    if content is None:
        return make.problem(
            "Es gibt kein viewport-Meta-Element. Mobilgeräte zeigen die Seite verkleinert wie eine Desktop-Seite.",
            value=None,
            where="<head>",
        )
    if _parse_viewport(content).get("width") != "device-width":
        return make.problem("viewport ohne width=device-width.", value=content, where="<meta name=viewport>", severity="mittel")
    return make.ok("viewport ist gesetzt.", value=content)


@check("meta.zoom", title="Zoom nicht gesperrt", severity="mittel")
def zoom(page, make):
    content = _viewport_content(page)
    if content is None:
        return make.ok("Ohne viewport-Angabe ist der Zoom nicht eingeschränkt.")
    values = _parse_viewport(content)
    blocked = []
    if values.get("user-scalable") in ("no", "0"):
        blocked.append(f"user-scalable={values['user-scalable']}")
    maximum = values.get("maximum-scale")
    if maximum:
        try:
            if float(maximum) < 2:
                blocked.append(f"maximum-scale={maximum}")
        except ValueError:
            pass
    if blocked:
        return make.problem(
            "Der Zoom ist eingeschränkt. Menschen mit Sehschwäche können Text nicht auf 200 Prozent vergrößern.",
            value=blocked,
            where="<meta name=viewport>",
        )
    return make.ok("Zoom ist nicht eingeschränkt.", value=content)


PSEUDO_CLASS = re.compile(r":(?:nth-[\w-]+\([^)]*\)|first-child|last-child|only-child|first-of-type|last-of-type|not\([^)]*\)|is\([^)]*\)|where\([^)]*\))")


def _base_selector(selector: str) -> str:
    return PSEUDO_CLASS.sub("", selector).strip()


def _px(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)px\s*", value)
    return float(match.group(1)) if match else None


@check("layout.overflow375", title="Horizontales Überlaufen bei 375 px (geschätzt)", severity="mittel")
def overflow375(page, make):
    hits: list[str] = []

    for node in page.soup.find_all(style=True):
        declarations = parse_declarations(node["style"])
        width = _px(declarations.get("width"))
        min_width = _px(declarations.get("min-width"))
        if min_width and min_width > VIEWPORT_WIDTH:
            hits.append(f"<{node.name} style> min-width {min_width:g}px")
        elif width and width > VIEWPORT_WIDTH and "max-width" not in declarations:
            hits.append(f"<{node.name} style> width {width:g}px")

    fluid_images = any(
        "img" in rule.selector.lower() and rule.declarations.get("max-width", "").strip() == "100%"
        for rule in page.all_rules()
    )
    for node in page.soup.find_all(["table", "img", "iframe", "video", "div", "td"], attrs={"width": True}):
        raw = str(node.get("width")).strip().removesuffix("px")
        if raw.isdigit() and int(raw) > VIEWPORT_WIDTH:
            if node.name == "img" and fluid_images:
                continue
            hits.append(f"<{node.name} width={raw}>")

    out_of_flow = {
        _base_selector(rule.selector)
        for rule in page.all_rules()
        if rule.declarations.get("position", "").strip() in ("absolute", "fixed")
    }
    for rule in page.all_rules():
        if rule.context and "@font-face" not in rule.context:
            continue
        if _base_selector(rule.selector) in out_of_flow:
            continue
        width = _px(rule.declarations.get("width"))
        min_width = _px(rule.declarations.get("min-width"))
        if min_width and min_width > VIEWPORT_WIDTH:
            hits.append(f"{rule.selector} min-width {min_width:g}px")
        elif width and width > VIEWPORT_WIDTH and "max-width" not in rule.declarations:
            hits.append(f"{rule.selector} width {width:g}px")
        if rule.declarations.get("white-space", "").strip() == "nowrap" and re.search(
            r"(^|[\s,>])(p|li|h[1-6])($|[\s,.:#\[])", rule.selector.lower()
        ):
            hits.append(f"{rule.selector} white-space nowrap")

    if hits:
        return make.problem(
            f"{len(hits)} Stellen mit fester Breite über {VIEWPORT_WIDTH} px gefunden. Das ist eine Schätzung ohne Browser, keine Messung.",
            value={"anzahl": len(hits), "beispiele": hits[:8]},
            estimate=True,
        )
    return make.ok(
        f"Keine festen Breiten über {VIEWPORT_WIDTH} px gefunden (Schätzung ohne Browser).",
        estimate=True,
    )
