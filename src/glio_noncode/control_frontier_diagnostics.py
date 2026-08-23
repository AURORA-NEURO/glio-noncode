"""Diagnostic findings over the control frontier evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierDiagnostic:
    diagnostic_id: str
    severity: str
    record_id: str | None
    code: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierDiagnostics:
    findings: tuple[ControlFrontierDiagnostic, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diagnose_control_frontier(evaluation: ControlFrontierEvaluation) -> ControlFrontierDiagnostics:
    findings = []
    for item in evaluation.executions:
        if item.issue_codes:
            body = {"diagnostic_id": f"{item.record_id}:issues", "severity": "review", "record_id": item.record_id, "code": item.issue_codes[0], "detail": "control issue remains visible for review"}
            findings.append(ControlFrontierDiagnostic(**body, content_address=content_hash(body)))
    if not findings:
        body = {"diagnostic_id": "none", "severity": "info", "record_id": None, "code": "no-issues", "detail": "all evaluated rows have empty issue tuples"}
        findings.append(ControlFrontierDiagnostic(**body, content_address=content_hash(body)))
    return ControlFrontierDiagnostics(tuple(findings), True, content_hash(tuple(findings)))


__all__ = ["ControlFrontierDiagnostic", "ControlFrontierDiagnostics", "diagnose_control_frontier"]
