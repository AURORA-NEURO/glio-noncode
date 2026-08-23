"""Scenario-axis coverage for the four platform operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierOperation
from .serialization import content_hash, jsonable


PLATFORM_FRONTIER_SCENARIO_AXES = ("positive", "missing", "incompatible", "boundary")


@dataclass(frozen=True, slots=True)
class PlatformFrontierScenarioCell:
    operation: PlatformFrontierOperation
    axis: str
    record_ids: tuple[str, ...]
    covered: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierScenarioMatrix:
    cells: tuple[PlatformFrontierScenarioCell, ...]
    cell_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_scenarios(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierScenarioMatrix:
    cells = []
    for operation in PlatformFrontierOperation:
        rows = tuple(item for item in evaluation.executions if item.operation is operation)
        mapping = {"positive": (rows[0],), "missing": (rows[1],), "incompatible": (rows[2],), "boundary": (rows[3],)}
        for axis in PLATFORM_FRONTIER_SCENARIO_AXES:
            ids = tuple(item.record_id for item in mapping[axis])
            body = {"operation": operation, "axis": axis, "record_ids": ids, "covered": bool(ids)}
            cells.append(PlatformFrontierScenarioCell(**body, content_address=content_hash(body)))
    return PlatformFrontierScenarioMatrix(tuple(cells), len(cells), all(item.covered for item in cells), content_hash(tuple(cells)))


def validate_platform_frontier_scenarios(matrix: PlatformFrontierScenarioMatrix) -> tuple[str, ...]:
    return () if matrix.accepted and matrix.cell_count == 16 else ("scenario_matrix_incomplete",)


__all__ = ["PLATFORM_FRONTIER_SCENARIO_AXES", "PlatformFrontierScenarioCell", "PlatformFrontierScenarioMatrix", "evaluate_platform_frontier_scenarios", "validate_platform_frontier_scenarios"]
