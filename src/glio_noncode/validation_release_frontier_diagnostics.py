"""Diagnostic findings derived from execution states and issue codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseDiagnostic:
    record_id: str
    severity: str
    code: str
    message: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseDiagnostics:
    findings: tuple[ValidationReleaseDiagnostic, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diagnose_validation_release(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseDiagnostics:
    findings = []
    for item in evaluation.executions:
        for code in item.issue_codes:
            severity = "blocking" if item.observed_state.value in {"blocked", "rejected"} else "review"
            body = {"record_id": item.record_id, "severity": severity, "code": code, "message": f"{code} remains visible for review"}
            findings.append(ValidationReleaseDiagnostic(**body, content_address=content_hash(body)))
    return ValidationReleaseDiagnostics(tuple(findings), True, content_hash(tuple(findings)))


__all__ = ["ValidationReleaseDiagnostic", "ValidationReleaseDiagnostics", "diagnose_validation_release"]
