"""State, issue, and cardinality metrics for platform evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierOperation, PlatformFrontierRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierOperationMetric:
    operation: PlatformFrontierOperation
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
class PlatformFrontierMetrics:
    fixture_id: str
    record_count: int
    accepted_count: int
    positive_count: int
    control_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operation_metrics: tuple[PlatformFrontierOperationMetric, ...]
    check_count: int
    passed_check_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_platform_frontier(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierMetrics:
    state_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    for row in evaluation.executions:
        state_counts[row.state.value] = state_counts.get(row.state.value, 0) + 1
        for issue in row.issue_codes:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    operation_metrics = []
    for operation in PlatformFrontierOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        states = {item.state.value: sum(row.state is item.state for row in rows) for item in rows}
        issues: dict[str, int] = {}
        for row in rows:
            for issue in row.issue_codes:
                issues[issue] = issues.get(issue, 0) + 1
        body = {"operation": operation, "record_count": len(rows), "positive_count": sum(item.role is PlatformFrontierRole.POSITIVE for item in rows), "control_count": sum(item.role is PlatformFrontierRole.CONTROL for item in rows), "accepted_count": sum(item.accepted for item in rows), "state_counts": states, "issue_counts": issues}
        operation_metrics.append(PlatformFrontierOperationMetric(**body, content_address=content_hash(body)))
    body = {"fixture_id": evaluation.fixture_id, "record_count": len(evaluation.executions), "accepted_count": sum(item.accepted for item in evaluation.executions), "positive_count": sum(item.role is PlatformFrontierRole.POSITIVE for item in evaluation.executions), "control_count": sum(item.role is PlatformFrontierRole.CONTROL for item in evaluation.executions), "state_counts": state_counts, "issue_counts": issue_counts, "operation_metrics": tuple(operation_metrics), "check_count": len(evaluation.checks), "passed_check_count": evaluation.passed_checks, "accepted": evaluation.accepted}
    return PlatformFrontierMetrics(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierMetrics", "PlatformFrontierOperationMetric", "measure_platform_frontier"]
