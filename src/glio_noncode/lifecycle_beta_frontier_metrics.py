"""State, operation, and control metrics for Domain 14 C05-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import (
    LifecycleBetaFrontierEvaluation,
    LifecycleBetaFrontierOperation,
    LifecycleBetaFrontierRole,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierOperationMetric:
    operation: LifecycleBetaFrontierOperation
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierMetrics:
    fixture_id: str
    operation_metrics: tuple[LifecycleBetaFrontierOperationMetric, ...]
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str

    def by_operation(self, operation: LifecycleBetaFrontierOperation | str) -> LifecycleBetaFrontierOperationMetric:
        selected = operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
        return next(item for item in self.operation_metrics if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_lifecycle_beta_frontier(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierMetrics:
    operation_metrics = []
    for operation in LifecycleBetaFrontierOperation:
        rows = evaluation.by_operation(operation)
        state_counts: dict[str, int] = {}
        issue_counts: dict[str, int] = {}
        for item in rows:
            state_counts[item.state.value] = state_counts.get(item.state.value, 0) + 1
            for issue in item.issue_codes:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        body = {
            "operation": operation,
            "record_count": len(rows),
            "positive_count": sum(item.role is LifecycleBetaFrontierRole.POSITIVE for item in rows),
            "control_count": sum(item.role is LifecycleBetaFrontierRole.CONTROL for item in rows),
            "accepted_count": sum(item.accepted for item in rows),
            "state_counts": dict(sorted(state_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
        }
        operation_metrics.append(LifecycleBetaFrontierOperationMetric(**body, content_address=content_hash(body)))
    states: dict[str, int] = {}
    issues: dict[str, int] = {}
    for item in evaluation.executions:
        states[item.state.value] = states.get(item.state.value, 0) + 1
        for issue in item.issue_codes:
            issues[issue] = issues.get(issue, 0) + 1
    body = {
        "fixture_id": evaluation.fixture_id,
        "operation_metrics": tuple(operation_metrics),
        "record_count": len(evaluation.executions),
        "positive_count": sum(item.role is LifecycleBetaFrontierRole.POSITIVE for item in evaluation.executions),
        "control_count": sum(item.role is LifecycleBetaFrontierRole.CONTROL for item in evaluation.executions),
        "accepted_count": sum(item.accepted for item in evaluation.executions),
        "state_counts": dict(sorted(states.items())),
        "issue_counts": dict(sorted(issues.items())),
    }
    return LifecycleBetaFrontierMetrics(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierMetrics", "LifecycleBetaFrontierOperationMetric", "measure_lifecycle_beta_frontier"]
