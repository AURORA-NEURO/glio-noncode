"""Positive/control coverage accounting for deployment operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierOperation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierControlCoverageRow:
    operation: DeploymentFrontierOperation
    positive_count: int
    control_count: int
    issue_count: int
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierControlCoverage:
    rows: tuple[DeploymentFrontierControlCoverageRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_control_coverage(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierControlCoverage:
    rows = []
    for operation in DeploymentFrontierOperation:
        selected = tuple(item for item in evaluation.executions if item.operation is operation)
        body = {"operation": operation, "positive_count": sum(item.role.value == "positive" for item in selected), "control_count": sum(item.role.value == "control" for item in selected), "issue_count": sum(bool(item.issue_codes) for item in selected), "complete": len(selected) == 4 and sum(item.role.value == "positive" for item in selected) == 1 and sum(item.role.value == "control" for item in selected) == 3}
        rows.append(DeploymentFrontierControlCoverageRow(**body, content_address=deployment_address(body)))
    return DeploymentFrontierControlCoverage(tuple(rows), all(item.complete for item in rows), deployment_address(tuple(rows)))


__all__ = ["DeploymentFrontierControlCoverage", "DeploymentFrontierControlCoverageRow", "build_deployment_frontier_control_coverage"]
