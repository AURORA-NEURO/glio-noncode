"""Expected-versus-observed reconciliation for coordination cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationEvaluation, CoordinationState, addressed


@dataclass(frozen=True, slots=True)
class CoordinationReconciliationItem:
    case_id: str
    expected_state: CoordinationState
    observed_state: CoordinationState
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "expected_issue_codes": self.expected_issue_codes,
            "observed_issue_codes": self.observed_issue_codes,
            "passed": self.passed,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CoordinationReconciliation:
    items: tuple[CoordinationReconciliationItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {"items": tuple(item.to_dict() for item in self.items), "accepted": self.accepted, "content_address": self.content_address}


def reconcile_coordination_evaluation(evaluation: CoordinationEvaluation, expected: dict[str, tuple[CoordinationState, tuple[str, ...]]]) -> CoordinationReconciliation:
    items = []
    for execution in evaluation.executions:
        expected_state, expected_issues = expected[execution.case_id]
        body = {
            "case_id": execution.case_id,
            "expected_state": expected_state,
            "observed_state": execution.observed_state,
            "expected_issue_codes": expected_issues,
            "observed_issue_codes": execution.issue_codes,
            "passed": expected_state is execution.observed_state and expected_issues == execution.issue_codes,
        }
        items.append(CoordinationReconciliationItem(**body, content_address=addressed(body, "coordination-reconciliation")))
    body = {"items": tuple(items), "accepted": all(item.passed for item in items)}
    return CoordinationReconciliation(**body, content_address=addressed(body, "coordination-reconciliation-report"))


__all__ = ["CoordinationReconciliationItem", "CoordinationReconciliation", "reconcile_coordination_evaluation"]
