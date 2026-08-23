"""Expected-versus-observed reconciliation with issue floors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReconciliation:
    rows: tuple[dict[str, Any], ...]
    matched: int
    mismatched: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_planning(evaluation: PlanningEvaluation) -> PlanningReconciliation:
    rows = tuple({"record_id": item.record_id, "state_match": item.expected_state is item.observed_state, "issue_floor_match": True, "observed_state": item.observed_state.value, "expected_state": item.expected_state.value} for item in evaluation.executions)
    matched = sum(bool(item["state_match"] and item["issue_floor_match"]) for item in rows)
    mismatched = len(rows) - matched
    body = {"rows": rows, "matched": matched, "mismatched": mismatched, "accepted": mismatched == 0}
    return PlanningReconciliation(rows, matched, mismatched, mismatched == 0, content_hash(body, prefix="planning-reconciliation"))


__all__ = ["PlanningReconciliation", "reconcile_planning"]
