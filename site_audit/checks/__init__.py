from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ..finding import Finding, Severity, Status, parse_severity
from ..page import Page


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    title: str
    severity: Severity
    func: Callable[[Page, "Maker"], Finding | Iterable[Finding] | None]

    @property
    def group(self) -> str:
        return self.check_id.split(".", 1)[0]


REGISTRY: dict[str, CheckSpec] = {}


class Maker:
    def __init__(self, spec: CheckSpec):
        self._spec = spec

    def _build(
        self,
        status: Status,
        message: str,
        value: Any,
        where: str | None,
        severity: Severity | str | None,
        estimate: bool,
    ) -> Finding:
        if severity is None:
            resolved = self._spec.severity
        elif isinstance(severity, Severity):
            resolved = severity
        else:
            resolved = parse_severity(severity)
        return Finding(
            check_id=self._spec.check_id,
            title=self._spec.title,
            severity=resolved,
            status=status,
            message=message,
            value=value,
            where=where,
            estimate=estimate,
        )

    def ok(self, message: str, value: Any = None, where: str | None = None, estimate: bool = False) -> Finding:
        return self._build(Status.OK, message, value, where, None, estimate)

    def problem(
        self,
        message: str,
        value: Any = None,
        where: str | None = None,
        severity: Severity | str | None = None,
        estimate: bool = False,
    ) -> Finding:
        return self._build(Status.PROBLEM, message, value, where, severity, estimate)

    def unknown(self, message: str, value: Any = None, where: str | None = None) -> Finding:
        return self._build(Status.UNKNOWN, message, value, where, None, False)


def check(check_id: str, *, title: str, severity: str = "mittel"):
    def decorator(func: Callable[[Page, Maker], Finding | Iterable[Finding] | None]):
        if check_id in REGISTRY:
            raise ValueError(f"Prüfung doppelt registriert: {check_id}")
        REGISTRY[check_id] = CheckSpec(check_id, title, parse_severity(severity), func)
        return func

    return decorator


def run_checks(page: Page, only: Iterable[str] | None = None) -> list[Finding]:
    selected = set(only) if only else None
    findings: list[Finding] = []
    for spec in REGISTRY.values():
        if selected and spec.check_id not in selected and spec.group not in selected:
            continue
        maker = Maker(spec)
        try:
            result = spec.func(page, maker)
        except Exception as exc:
            findings.append(maker.unknown(f"Prüfung ist fehlgeschlagen: {type(exc).__name__}: {exc}"))
            continue
        if result is None:
            continue
        if isinstance(result, Finding):
            findings.append(result)
        else:
            findings.extend(result)
    return findings


from . import tls, meta, legal, privacy, a11y, perf, content, seo, security
