from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "kritisch"
    HIGH = "hoch"
    MEDIUM = "mittel"
    NOTE = "hinweis"

    @property
    def rank(self) -> int:
        return SEVERITY_ORDER.index(self)


SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.NOTE]


def parse_severity(text: str) -> Severity:
    for severity in Severity:
        if severity.value == text:
            return severity
    raise ValueError(f"unbekannter Schweregrad: {text}")


class Status(str, Enum):
    OK = "ok"
    PROBLEM = "problem"
    UNKNOWN = "unbekannt"


@dataclass(frozen=True)
class Finding:
    check_id: str
    title: str
    severity: Severity
    status: Status
    message: str
    value: Any = None
    where: str | None = None
    estimate: bool = False

    @property
    def is_problem(self) -> bool:
        return self.status is Status.PROBLEM

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "title": self.title,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "value": _jsonable(self.value),
            "where": self.where,
            "estimate": self.estimate,
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def sort_key(finding: Finding) -> tuple[int, int, str]:
    status_rank = {Status.PROBLEM: 0, Status.UNKNOWN: 1, Status.OK: 2}[finding.status]
    severity_rank = finding.severity.rank if finding.status is Status.PROBLEM else 0
    return (status_rank, severity_rank, finding.check_id)
