"""Cross-plane validation matrix for control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .serialization import content_hash, jsonable


CONTROL_FRONTIER_VALIDATION_PLANES = ("policy", "resource", "provenance", "replay")


@dataclass(frozen=True, slots=True)
class ControlFrontierValidationCell:
    record_id: str
    plane: str
    observed: Any
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierValidationMatrix:
    fixture_id: str
    cells: tuple[ControlFrontierValidationCell, ...]
    accepted: bool
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"cell_count": self.cell_count}


def build_control_frontier_validation_matrix(evaluation: ControlFrontierEvaluation) -> ControlFrontierValidationMatrix:
    cells = []
    for execution in evaluation.executions:
        for plane in CONTROL_FRONTIER_VALIDATION_PLANES:
            passed = bool(execution.content_address and execution.output)
            body = {"record_id": execution.record_id, "plane": plane, "observed": execution.state.value, "passed": passed}
            cells.append(ControlFrontierValidationCell(**body, content_address=content_hash(body)))
    accepted = len(cells) == len(evaluation.executions) * len(CONTROL_FRONTIER_VALIDATION_PLANES) and all(item.passed for item in cells)
    body = {"fixture_id": evaluation.fixture_id, "cells": tuple(cells), "accepted": accepted}
    return ControlFrontierValidationMatrix(**body, content_address=content_hash(body))


def validate_control_frontier_matrix(matrix: ControlFrontierValidationMatrix) -> tuple[str, ...]:
    issues = []
    if any(item.plane not in CONTROL_FRONTIER_VALIDATION_PLANES for item in matrix.cells):
        issues.append("unknown_plane")
    if not matrix.cells:
        issues.append("empty_matrix")
    return tuple(issues)


__all__ = ["CONTROL_FRONTIER_VALIDATION_PLANES", "ControlFrontierValidationCell", "ControlFrontierValidationMatrix", "build_control_frontier_validation_matrix", "validate_control_frontier_matrix"]
