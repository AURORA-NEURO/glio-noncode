"""State, issue, and operation metrics for deployment frontier runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierOperation
from .deployment_frontier_support import count_states, deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOperationMetric:
    operation: DeploymentFrontierOperation
    record_count: int
    positive_count: int
    control_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    accepted_rate: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierMetrics:
    record_count: int
    positive_count: int
    control_count: int
    operation_metrics: tuple[DeploymentFrontierOperationMetric, ...]
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_deployment_frontier(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierMetrics:
    metrics = []
    for operation in DeploymentFrontierOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        positive = sum(item.role.value == "positive" for item in rows)
        controls = len(rows) - positive
        issue_counts: dict[str, int] = {}
        for row in rows:
            for issue in row.issue_codes:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        body = {
            "operation": operation,
            "record_count": len(rows),
            "positive_count": positive,
            "control_count": controls,
            "state_counts": count_states(rows),
            "issue_counts": dict(sorted(issue_counts.items())),
            "accepted_rate": round(sum(item.accepted for item in rows) / max(1, len(rows)), 6),
        }
        metrics.append(DeploymentFrontierOperationMetric(**body, content_address=deployment_address(body)))
    issues: dict[str, int] = {}
    for row in evaluation.executions:
        for issue in row.issue_codes:
            issues[issue] = issues.get(issue, 0) + 1
    body = {
        "record_count": len(evaluation.executions),
        "positive_count": sum(item.role.value == "positive" for item in evaluation.executions),
        "control_count": sum(item.role.value == "control" for item in evaluation.executions),
        "operation_metrics": tuple(metrics),
        "state_counts": count_states(evaluation.executions),
        "issue_counts": dict(sorted(issues.items())),
    }
    return DeploymentFrontierMetrics(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierMetrics", "DeploymentFrontierOperationMetric", "measure_deployment_frontier"]
