"""Coverage and disposition metrics for the planning frontier."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningMetrics:
    fixture_id: str
    operation_counts: dict[str, int]
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    plane_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_planning(evaluation: PlanningEvaluation) -> PlanningMetrics:
    operations = Counter(item.operation.value for item in evaluation.executions)
    states = Counter(item.observed_state.value for item in evaluation.executions)
    issues = Counter(code for item in evaluation.executions for code in item.issue_codes)
    planes = Counter(item.plane for item in evaluation.checks)
    body = {"fixture_id": evaluation.fixture_id, "operation_counts": dict(operations), "state_counts": dict(states), "issue_counts": dict(issues), "plane_counts": dict(planes), "accepted": evaluation.accepted}
    return PlanningMetrics(evaluation.fixture_id, dict(operations), dict(states), dict(issues), dict(planes), evaluation.accepted, content_hash(body, prefix="planning-metrics"))


__all__ = ["PlanningMetrics", "measure_planning"]
