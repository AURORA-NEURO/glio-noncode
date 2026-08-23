"""Scenario-axis coverage for deployment governance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierOperation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


DEPLOYMENT_FRONTIER_SCENARIO_AXES = ("positive", "missing_input", "policy_boundary", "context_boundary")


@dataclass(frozen=True, slots=True)
class DeploymentFrontierScenarioCell:
    scenario_id: str
    operation: DeploymentFrontierOperation
    axis: str
    observed_state: str
    expected_review: bool
    covered: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierScenarioMatrix:
    cells: tuple[DeploymentFrontierScenarioCell, ...]
    accepted: bool
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_deployment_frontier_scenarios(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierScenarioMatrix:
    cells = []
    for operation in DeploymentFrontierOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        positive = next((item for item in rows if item.role.value == "positive"), rows[0])
        controls = tuple(item for item in rows if item.role.value == "control")
        selected = (positive,) + controls
        for axis, row in zip(DEPLOYMENT_FRONTIER_SCENARIO_AXES, selected, strict=True):
            body = {"scenario_id": f"{operation.value}:{axis}", "operation": operation, "axis": axis, "observed_state": row.state.value, "expected_review": axis != "positive", "covered": bool(row.issue_codes) == (axis != "positive")}
            cells.append(DeploymentFrontierScenarioCell(**body, content_address=deployment_address(body)))
    return DeploymentFrontierScenarioMatrix(tuple(cells), len(cells) == 16 and all(item.covered for item in cells), deployment_address(tuple(cells)))


def validate_deployment_frontier_scenarios(matrix: DeploymentFrontierScenarioMatrix) -> tuple[str, ...]:
    return tuple(item.scenario_id for item in matrix.cells if not item.covered)


__all__ = ["DEPLOYMENT_FRONTIER_SCENARIO_AXES", "DeploymentFrontierScenarioCell", "DeploymentFrontierScenarioMatrix", "evaluate_deployment_frontier_scenarios", "validate_deployment_frontier_scenarios"]
