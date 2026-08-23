"""State, issue, role, and operation metrics for control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierOperationMetric:
    operation: ControlFrontierOperation
    record_count: int
    accepted_count: int
    control_count: int
    issue_count: int
    state_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierMetrics:
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operation_metrics: tuple[ControlFrontierOperationMetric, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_control_frontier(evaluation: ControlFrontierEvaluation) -> ControlFrontierMetrics:
    """Measure every row without suppressing control outcomes."""

    state_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    operation_metrics: list[ControlFrontierOperationMetric] = []
    for operation in ControlFrontierOperation:
        rows = evaluation.by_operation(operation)
        states: dict[str, int] = {}
        for row in rows:
            states[row.state.value] = states.get(row.state.value, 0) + 1
            state_counts[row.state.value] = state_counts.get(row.state.value, 0) + 1
            for issue in row.issue_codes:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        body = {"operation": operation, "record_count": len(rows), "accepted_count": sum(item.accepted for item in rows), "control_count": sum(item.role.value == "control" for item in rows), "issue_count": sum(len(item.issue_codes) for item in rows), "state_counts": dict(sorted(states.items()))}
        operation_metrics.append(ControlFrontierOperationMetric(**body, content_address=content_hash(body)))
    body = {"record_count": len(evaluation.executions), "positive_count": sum(item.role.value == "positive" for item in evaluation.executions), "control_count": sum(item.role.value == "control" for item in evaluation.executions), "accepted_count": sum(item.accepted for item in evaluation.executions), "state_counts": dict(sorted(state_counts.items())), "issue_counts": dict(sorted(issue_counts.items())), "operation_metrics": tuple(operation_metrics)}
    return ControlFrontierMetrics(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierMetrics", "ControlFrontierOperationMetric", "measure_control_frontier"]
