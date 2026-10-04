from __future__ import annotations

import re

from ..css import contrast_ratio, collect_variables, first_color_in, parse_color, resolve_variables
from . import check

LANG_PATTERN = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")


@check("a11y.alt", title="Bilder mit Alternativtext", severity="mittel")
def alt_texts(page, make):
    images = page.soup.find_all("img")
    if not images:
        return make.ok("Die Seite enthält keine Bilder im HTML.", value={"ohne_alt": 0, "gesamt": 0})
    missing = [
        img
        for img in images
        if img.get("alt") is None and img.get("role") != "presentation" and img.get("aria-hidden") != "true"
    ]
    value = {"ohne_alt": len(missing), "gesamt": len(images)}
    if missing:
        return make.problem(
            f"{len(missing)} von {len(images)} Bildern haben kein alt-Attribut.",
            value=value,
            where=", ".join((img.get("src") or "ohne src")[:60] for img in missing[:5]),
        )
    summary = "Das einzige Bild hat ein alt-Attribut." if len(images) == 1 else f"Alle {len(images)} Bilder haben ein alt-Attribut."
    return make.ok(summary, value=value)


@check("a11y.lang", title="Sprache der Seite angegeben", severity="mittel")
def language(page, make):
    html = page.soup.find("html")
    lang = (html.get("lang") if html else None) or ""
    lang = lang.strip()
    if not lang:
        return make.problem("Das html-Element hat kein lang-Attribut. Vorlesegeräte wählen die Sprache dann selbst.", value=None, where="<html>")
    if not LANG_PATTERN.match(lang):
        return make.problem(f"Der Wert von lang ist keine gültige Sprachangabe: {lang}", value=lang, where="<html>", severity="hinweis")
    return make.ok(f"Sprache: {lang}", value=lang)


@check("a11y.headings", title="Überschriftenstruktur", severity="mittel")
def headings(page, make):
    nodes = page.soup.find_all(re.compile(r"^h[1-6]$"))
    levels = [int(n.name[1]) for n in nodes]
    problems: list[str] = []
    severity = "hinweis"
    if not levels:
        return make.problem("Die Seite hat keine Überschriften.", value=[], severity="mittel")
    h1_count = levels.count(1)
    if h1_count == 0:
        problems.append("keine h1")
        severity = "mittel"
    elif h1_count > 1:
        problems.append(f"{h1_count} Mal h1")
    for before, after in zip(levels, levels[1:]):
        if after - before > 1:
            problems.append(f"Sprung von h{before} auf h{after}")
    if problems:
        return make.problem("Die Überschriftenstruktur hat Lücken: " + "; ".join(problems[:6]) + ".", value=problems, severity=severity)
    return make.ok(f"{len(levels)} Überschriften ohne Sprünge.", value=levels)


SKIP_SELECTOR = re.compile(r":(hover|focus|active|disabled|visited)|::?placeholder|::selection", re.I)
PAGE_SELECTORS = {"html", "body", ":root"}


@check("a11y.contrast", title="Kontrast der Textfarben (aus dem CSS)", severity="mittel")
def contrast(page, make):
    rules = [r for r in page.all_rules() if "prefers-color-scheme" not in r.context and "keyframes" not in r.context]
    variables = collect_variables(rules)

    def color(rule, *names):
        for name in names:
            value = rule.declarations.get(name)
            if value:
                resolved = resolve_variables(value, variables)
                parsed = first_color_in(resolved) if name == "background" else parse_color(resolved)
                if parsed:
                    return parsed
        return None

    page_fg = None
    page_bg = None
    for rule in rules:
        if {s.strip().lower() for s in rule.selector.split(",")} & PAGE_SELECTORS:
            page_fg = color(rule, "color") or page_fg
            page_bg = color(rule, "background-color", "background") or page_bg

    measured: list[tuple[float, str]] = []
    if page_fg is not None or page_bg is not None:
        measured.append((contrast_ratio(page_fg or (0, 0, 0), page_bg or (255, 255, 255)), "Seitenhintergrund (html, body)"))
    for rule in rules:
        if SKIP_SELECTOR.search(rule.selector):
            continue
        if {s.strip().lower() for s in rule.selector.split(",")} & PAGE_SELECTORS:
            continue
        fg = color(rule, "color")
        bg = color(rule, "background-color", "background")
        if fg is None or bg is None:
            continue
        measured.append((contrast_ratio(fg, bg), rule.selector.strip()[:60]))

    if not measured:
        return make.unknown("Im CSS steht kein Farbpaar aus Textfarbe und Hintergrund im selben Block (Variablen, Verläufe, Stile in Fremddateien).")
    measured.sort()
    worst_ratio, worst_selector = measured[0]
    failing = [(r, s) for r, s in measured if r < 4.5]
    value = {"niedrigster": round(worst_ratio, 2), "bei": worst_selector, "gemessen": len(measured), "darunter": len(failing)}
    if failing:
        severity = "hoch" if worst_ratio < 3 else "mittel"
        count = "liegt 1 Farbpaar" if len(failing) == 1 else f"liegen {len(failing)} Farbpaare"
        return make.problem(
            f"Von {len(measured)} gemessenen Farbpaaren {count} unter dem Verhältnis 4,5:1. Niedrigster Wert {worst_ratio:.2f}:1 bei {worst_selector}.",
            value=value,
            where=worst_selector,
            severity=severity,
        )
    return make.ok(f"Niedrigster gemessener Kontrast {worst_ratio:.2f}:1 bei {len(measured)} Farbpaaren.", value=value)
