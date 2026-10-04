from __future__ import annotations

import json

from ..audit import AuditResult


def render(result: AuditResult) -> str:
    counts = result.count_by_severity()
    document = {
        "werkzeug": f"site-audit {result.version}",
        "adresse": result.requested_url,
        "endadresse": result.final_url,
        "zeitpunkt": result.started_at.isoformat(),
        "zusammenfassung": {
            "probleme": {severity.value: count for severity, count in counts.items()},
            "bestanden": len(result.passed),
            "unbekannt": len(result.unknown),
        },
        "hinweise": result.warnings,
        "befunde": [finding.to_dict() for finding in result.findings],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
