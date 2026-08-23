"""Diagnostic summaries for held rows and operation behavior."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningDiagnostic:
    diagnostic_id: str
    severity: str
    operation: str
    record_id: str
    code: str
    detail: str
    remediation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningDiagnosticReport:
    diagnostics: tuple[PlanningDiagnostic, ...]
    counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


REMEDIATIONS = {
    "context_mismatch": "verify the exact context key and source scope",
    "context_not_declared_supported": "obtain a source declaration for the requested context",
    "invalid_guide_oligo_row": "repair the row and retain the original quarantine reason",
    "missing_target_id": "supply a stable target identity before planning assignments",
    "invalid_power_row": "supply finite non-zero effect and positive variance values",
    "no_model_observations": "abstain until a public aggregate model observation is available",
    "empty_source": "abstain until a public guide source is available",
    "no_targets": "abstain until context-closed target identities are available",
    "no_power_observations": "abstain until a power observation is available",
}


def build_planning_diagnostics(evaluation: PlanningEvaluation) -> PlanningDiagnosticReport:
    diagnostics = []
    for execution in evaluation.executions:
        for code in execution.issue_codes:
            severity = "blocking" if code == "context_mismatch" else "review"
            detail = f"{execution.operation.value} returned {code} for {execution.record_id}"
            body = {
                "diagnostic_id": f"diagnostic:{execution.record_id}:{code}",
                "severity": severity,
                "operation": execution.operation.value,
                "record_id": execution.record_id,
                "code": code,
                "detail": detail,
                "remediation": REMEDIATIONS.get(code, "retain the issue code and route to review"),
            }
            diagnostics.append(PlanningDiagnostic(**body, content_address=content_hash(body, prefix="planning-diagnostic")))
    values = tuple(diagnostics)
    counts = dict(Counter(item.code for item in values))
    accepted = all(item.remediation for item in values)
    body = {"diagnostics": values, "counts": counts, "accepted": accepted}
    return PlanningDiagnosticReport(values, counts, accepted, content_hash(body, prefix="planning-diagnostics"))


__all__ = ["PlanningDiagnostic", "PlanningDiagnosticReport", "build_planning_diagnostics"]
