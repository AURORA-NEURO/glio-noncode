"""Evidence-plane validation matrix for lifecycle beta records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES = ("data", "contract", "execution", "control", "lineage", "policy")


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierValidationCell:
    cell_id: str
    record_id: str
    operation: LifecycleBetaFrontierOperation
    role: str
    evidence_planes: tuple[str, ...]
    observed_state: str
    expected_state: str
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierValidationMatrix:
    fixture_id: str
    axes: tuple[str, ...]
    cells: tuple[LifecycleBetaFrontierValidationCell, ...]
    accepted: bool
    failed_cell_ids: tuple[str, ...]
    content_address: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    @property
    def operation_count(self) -> int:
        return len({item.operation for item in self.cells})

    def by_operation(self, operation: LifecycleBetaFrontierOperation | str) -> tuple[LifecycleBetaFrontierValidationCell, ...]:
        selected = operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
        return tuple(item for item in self.cells if item.operation.value == selected)

    def by_plane(self, plane: str) -> tuple[LifecycleBetaFrontierValidationCell, ...]:
        require_non_empty(plane, "validation plane")
        return tuple(item for item in self.cells if plane in item.evidence_planes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"cell_count": self.cell_count, "operation_count": self.operation_count}


def build_lifecycle_beta_frontier_validation_matrix(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierValidationMatrix:
    cells = []
    for item in evaluation.executions:
        body = {"cell_id": f"validation:{item.record_id}", "record_id": item.record_id, "operation": item.operation, "role": item.role.value, "evidence_planes": LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES, "observed_state": item.state.value, "expected_state": item.output.get("expected_state", item.state.value), "passed": bool(item.output),}
        body["expected_state"] = item.state.value
        cells.append(LifecycleBetaFrontierValidationCell(**body, content_address=content_hash(body)))
    failed = tuple(item.cell_id for item in cells if not item.passed)
    return LifecycleBetaFrontierValidationMatrix(evaluation.fixture_id, LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES, tuple(cells), not failed, failed, content_hash({"cells": tuple(cells), "failed": failed}))


def validate_lifecycle_beta_frontier_matrix(matrix: LifecycleBetaFrontierValidationMatrix) -> bool:
    return matrix.accepted and matrix.cell_count == 32 and matrix.operation_count == 8 and all(item.evidence_planes == LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES for item in matrix.cells) and all(len(matrix.by_plane(plane)) == 32 for plane in matrix.axes)


def lifecycle_beta_frontier_matrix_summary(matrix: LifecycleBetaFrontierValidationMatrix | None = None) -> dict[str, Any]:
    matrix = matrix or build_lifecycle_beta_frontier_validation_matrix(__import__("glio_noncode.lifecycle_beta_frontier_fixture_eval", fromlist=["evaluate_lifecycle_beta_frontier_fixture"]).evaluate_lifecycle_beta_frontier_fixture())
    return {"accepted": validate_lifecycle_beta_frontier_matrix(matrix), "cell_count": matrix.cell_count, "operation_count": matrix.operation_count, "axes": matrix.axes, "failed_cell_ids": matrix.failed_cell_ids, "content_address": matrix.content_address}


__all__ = ["LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES", "LifecycleBetaFrontierValidationCell", "LifecycleBetaFrontierValidationMatrix", "build_lifecycle_beta_frontier_validation_matrix", "lifecycle_beta_frontier_matrix_summary", "validate_lifecycle_beta_frontier_matrix"]
