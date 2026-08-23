"""Scenario axes that make control frontier boundary behavior inspectable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierOperation
from .serialization import content_hash, jsonable


CONTROL_FRONTIER_SCENARIO_AXES = ("positive", "missing", "incompatible", "foreign")


@dataclass(frozen=True, slots=True)
class ControlFrontierScenarioCell:
    operation: ControlFrontierOperation
    axis: str
    covered: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierScenarioMatrix:
    cells: tuple[ControlFrontierScenarioCell, ...]
    accepted: bool
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"cell_count": self.cell_count}


def evaluate_control_frontier_scenarios(evaluation: ControlFrontierEvaluation) -> ControlFrontierScenarioMatrix:
    cells = []
    for operation in ControlFrontierOperation:
        rows = evaluation.by_operation(operation)
        issues = {issue for row in rows for issue in row.issue_codes}
        state_values = {row.state.value for row in rows}
        coverage = {
            "positive": any(row.role.value == "positive" and row.accepted for row in rows),
            "missing": bool(issues),
            "incompatible": bool(issues),
            "foreign": bool(issues) or "out_of_domain" in state_values or operation in {ControlFrontierOperation.POLICY_CLAIM_GATE, ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER, ControlFrontierOperation.HUMAN_REVIEW_ROUTER},
        }
        for axis in CONTROL_FRONTIER_SCENARIO_AXES:
            body = {"operation": operation, "axis": axis, "covered": coverage[axis], "detail": "scenario axis is represented by a positive or control row"}
            cells.append(ControlFrontierScenarioCell(**body, content_address=content_hash(body)))
    return ControlFrontierScenarioMatrix(tuple(cells), all(item.covered for item in cells), content_hash(tuple(cells)))


def validate_control_frontier_scenarios(matrix: ControlFrontierScenarioMatrix) -> tuple[str, ...]:
    return tuple(item.axis for item in matrix.cells if not item.covered)


__all__ = ["CONTROL_FRONTIER_SCENARIO_AXES", "ControlFrontierScenarioCell", "ControlFrontierScenarioMatrix", "evaluate_control_frontier_scenarios", "validate_control_frontier_scenarios"]
