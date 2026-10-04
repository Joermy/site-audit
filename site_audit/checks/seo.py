from __future__ import annotations

import re

from . import check


@check("seo.title", title="Seitentitel vorhanden und passend lang", severity="mittel")
def title(page, make):
    node = page.soup.find("title")
    text = re.sub(r"\s+", " ", node.get_text()).strip() if node else ""
    if not text:
        return make.problem("Die Seite hat keinen title.", value=0, where="<head>")
    length = len(text)
    if length < 10 or length > 65:
        return make.problem(
            f"Der Titel hat {length} Zeichen. Üblich sind etwa 10 bis 65.",
            value={"zeichen": length, "text": text},
            severity="hinweis",
        )
    return make.ok(f"Titel mit {length} Zeichen.", value={"zeichen": length, "text": text})


@check("seo.description", title="Seitenbeschreibung vorhanden", severity="hinweis")
def description(page, make):
    node = page.soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    text = (node.get("content") or "").strip() if node else ""
    if not text:
        return make.problem("Es gibt keine meta description.", value=0, where="<head>")
    length = len(text)
    if length < 50 or length > 170:
        return make.problem(f"Die Beschreibung hat {length} Zeichen. Üblich sind etwa 50 bis 170.", value=length)
    return make.ok(f"Beschreibung mit {length} Zeichen.", value=length)
