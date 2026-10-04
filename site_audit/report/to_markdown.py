from __future__ import annotations

from ..audit import AuditResult
from ..finding import SEVERITY_ORDER, Finding


def _value(value) -> str:
    from . import format_value

    return format_value(value).replace("|", "\\|").replace("\n", " ")


def _problem_block(finding: Finding) -> list[str]:
    lines = [f"### [{finding.severity.value}] `{finding.check_id}` — {finding.title}", "", finding.message, ""]
    if finding.value not in (None, "", [], {}):
        lines.append(f"- Messwert: {_value(finding.value)}")
    if finding.where:
        lines.append(f"- Fundstelle: {finding.where}")
    if finding.estimate:
        lines.append("- Das ist eine Schätzung, keine Messung.")
    if lines[-1] != "":
        lines.append("")
    return lines


def render(result: AuditResult) -> str:
    counts = result.count_by_severity()
    lines = [
        f"# Prüfbericht für {result.final_url}",
        "",
        f"Erstellt am {result.started_at.strftime('%d.%m.%Y %H:%M')} UTC mit site-audit {result.version}.",
        "",
        "## Zusammenfassung",
        "",
        "| Schweregrad | Anzahl |",
        "|---|---:|",
    ]
    for severity in SEVERITY_ORDER:
        lines.append(f"| {severity.value} | {counts[severity]} |")
    lines += [
        "",
        f"Bestanden: {len(result.passed)} · Nicht bestimmbar: {len(result.unknown)}",
        "",
    ]
    if result.warnings:
        lines += ["## Einschränkungen dieses Laufs", ""]
        lines += [f"- {warning}" for warning in result.warnings]
        lines.append("")

    if result.problems:
        lines += ["## Befunde", ""]
        for finding in result.problems:
            lines += _problem_block(finding)
    else:
        lines += ["## Befunde", "", "Keine Auffälligkeiten gefunden.", ""]

    if result.unknown:
        lines += ["## Nicht bestimmbar", "", "| Prüfung | Grund |", "|---|---|"]
        for finding in result.unknown:
            lines.append(f"| `{finding.check_id}` | {_value(finding.message)} |")
        lines.append("")

    if result.passed:
        lines += ["## Bestanden", "", "| Prüfung | Ergebnis | Messwert |", "|---|---|---|"]
        for finding in result.passed:
            lines.append(f"| `{finding.check_id}` | {_value(finding.message)} | {_value(finding.value)} |")
        lines.append("")

    lines += [
        "---",
        "",
        "Dieser Bericht beschreibt technische Beobachtungen auf der Startseite. Er ist keine Rechtsberatung.",
        "Es wurde kein JavaScript ausgeführt.",
        "",
    ]
    return "\n".join(lines)
