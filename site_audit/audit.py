from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from . import __version__
from .checks import REGISTRY, run_checks
from .fetch import Network
from .finding import SEVERITY_ORDER, Finding, Severity, Status, sort_key
from .page import load_page


@dataclass
class AuditResult:
    requested_url: str
    final_url: str
    started_at: datetime
    findings: list[Finding]
    warnings: list[str] = field(default_factory=list)
    version: str = __version__

    @property
    def problems(self) -> list[Finding]:
        return [f for f in self.findings if f.status is Status.PROBLEM]

    @property
    def passed(self) -> list[Finding]:
        return [f for f in self.findings if f.status is Status.OK]

    @property
    def unknown(self) -> list[Finding]:
        return [f for f in self.findings if f.status is Status.UNKNOWN]

    def count_by_severity(self) -> dict[Severity, int]:
        counts = {severity: 0 for severity in SEVERITY_ORDER}
        for finding in self.problems:
            counts[finding.severity] += 1
        return counts

    def worst(self) -> Severity | None:
        problems = self.problems
        return min((f.severity for f in problems), key=lambda s: s.rank) if problems else None


def run_audit(
    url: str,
    net: Network,
    *,
    max_resources: int = 60,
    only: Iterable[str] | None = None,
    now: datetime | None = None,
) -> AuditResult:
    started = now or datetime.now(timezone.utc)
    page = load_page(url, net, max_resources=max_resources, now=started)
    findings = sorted(run_checks(page, only), key=sort_key)
    return AuditResult(
        requested_url=page.requested_url,
        final_url=page.url,
        started_at=started,
        findings=findings,
        warnings=list(page.warnings),
    )


def available_checks() -> list[tuple[str, str, str]]:
    return [(spec.check_id, spec.severity.value, spec.title) for spec in REGISTRY.values()]
