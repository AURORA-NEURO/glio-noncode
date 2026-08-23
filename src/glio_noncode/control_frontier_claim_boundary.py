"""Claim-boundary checks that prevent operational states becoming conclusions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierClaimBoundaryCheck:
    check_id: str
    passed: bool
    observed: Any
    prohibited: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierClaimBoundaryReport:
    checks: tuple[ControlFrontierClaimBoundaryCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_control_frontier_claim_boundary(evaluation: ControlFrontierEvaluation) -> ControlFrontierClaimBoundaryReport:
    prohibited_terms = ("clinical", "patient ranking", "treatment", "autonomous action")
    observed_text = " ".join(str(item.output) for item in evaluation.executions).lower()
    values = (
        ("no-prohibited-claim", not any(term in observed_text for term in prohibited_terms), prohibited_terms, "operation receipts contain no prohibited claim language"),
        ("states-are-operational", all(item.state in set(ControlFrontierState) for item in evaluation.executions), "operational state enum", "states remain within the explicit vocabulary"),
        ("controls-not-success", all(item.role.value == "positive" or not item.accepted for item in evaluation.executions), True, "controls cannot be accepted as positive outputs"),
    )
    checks = []
    for check_id, passed, prohibited, detail in values:
        body = {"check_id": check_id, "passed": passed, "observed": True if passed else observed_text, "prohibited": prohibited, "detail": detail}
        checks.append(ControlFrontierClaimBoundaryCheck(**body, content_address=content_hash(body)))
    return ControlFrontierClaimBoundaryReport(tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["ControlFrontierClaimBoundaryCheck", "ControlFrontierClaimBoundaryReport", "evaluate_control_frontier_claim_boundary"]
