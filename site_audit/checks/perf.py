from __future__ import annotations

from collections import defaultdict

from . import check

TARGET_BYTES = 800 * 1024
LIMIT_BYTES = 1500 * 1024
HEAVY_BYTES = 4000 * 1024
REQUEST_NOTE = 50
REQUEST_LIMIT = 80
REQUEST_HEAVY = 120


def _kb(size: int) -> str:
    return f"{size / 1024:.0f} KB"


@check("perf.weight", title="Gewicht der Seite", severity="mittel")
def weight(page, make):
    by_kind: dict[str, int] = defaultdict(int)
    by_kind["html"] = page.html_bytes
    unmeasured = 0
    for resource in page.resources:
        if resource.external:
            continue
        if resource.size is None:
            unmeasured += 1
            continue
        by_kind[resource.kind] += resource.size
    total = sum(by_kind.values())
    value = {**{kind: size for kind, size in sorted(by_kind.items())}, "gesamt": total}
    note = " Fremde Ressourcen sind nicht eingerechnet."
    if unmeasured:
        note += f" {unmeasured} eigene Ressourcen waren nicht messbar."
    if total > HEAVY_BYTES:
        return make.problem(f"Die Seite wiegt {_kb(total)}.{note}", value=value, severity="hoch")
    if total > LIMIT_BYTES:
        return make.problem(f"Die Seite wiegt {_kb(total)}, die Grenze liegt bei {_kb(LIMIT_BYTES)}.{note}", value=value)
    if total > TARGET_BYTES:
        return make.problem(f"Die Seite wiegt {_kb(total)}, das Ziel liegt bei {_kb(TARGET_BYTES)}.{note}", value=value, severity="hinweis")
    return make.ok(f"Die Seite wiegt {_kb(total)}.{note}", value=value)


@check("perf.requests", title="Anzahl der Anfragen", severity="mittel")
def requests(page, make):
    total = 1 + len(page.resources)
    external = sum(1 for r in page.resources if r.external)
    value = {"gesamt": total, "eigene": total - external, "fremde": external}
    if total > REQUEST_HEAVY:
        return make.problem(f"{total} Anfragen für eine Seite.", value=value, severity="hoch")
    if total > REQUEST_LIMIT:
        return make.problem(f"{total} Anfragen für eine Seite.", value=value)
    if total > REQUEST_NOTE:
        return make.problem(f"{total} Anfragen für eine Seite.", value=value, severity="hinweis")
    return make.ok(f"{total} Anfragen.", value=value)
