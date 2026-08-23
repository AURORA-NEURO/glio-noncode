"""Validation-plane matrix covering every deployment fixture row."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierEvaluation
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


DEPLOYMENT_FRONTIER_VALIDATION_PLANES = ("contract", "state", "control", "output")


@dataclass(frozen=True, slots=True)
class DeploymentFrontierValidationCell:
    cell_id: str
    record_id: str
    plane: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierValidationMatrix:
    cells: tuple[DeploymentFrontierValidationCell, ...]
    accepted: bool
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_validation_matrix(evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierValidationMatrix:
    cells = []
    for execution in evaluation.executions:
        values = (True, bool(execution.state.value), bool(execution.issue_codes) == (execution.role.value == "control"), execution.content_address.startswith("sha256:"))
        for plane, passed in zip(DEPLOYMENT_FRONTIER_VALIDATION_PLANES, values, strict=True):
            body = {"cell_id": f"{execution.record_id}:{plane}", "record_id": execution.record_id, "plane": plane, "passed": passed, "detail": f"{plane} plane retained for {execution.operation.value}"}
            cells.append(DeploymentFrontierValidationCell(**body, content_address=deployment_address(body)))
    return DeploymentFrontierValidationMatrix(tuple(cells), len(cells) == 64 and all(item.passed for item in cells), deployment_address(tuple(cells)))


def validate_deployment_frontier_matrix(matrix: DeploymentFrontierValidationMatrix) -> tuple[str, ...]:
    return tuple(item.cell_id for item in matrix.cells if not item.passed)


__all__ = ["DEPLOYMENT_FRONTIER_VALIDATION_PLANES", "DeploymentFrontierValidationCell", "DeploymentFrontierValidationMatrix", "build_deployment_frontier_validation_matrix", "validate_deployment_frontier_matrix"]
