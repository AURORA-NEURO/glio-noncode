"""Operation and outcome acceptance matrix for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierOperation, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAcceptanceCell:
    operation: str
    expected_state: str
    observed_count: int
    expected_count: int
    accepted: bool
    control_count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAcceptanceMatrix:
    fixture_id: str
    cells: tuple[LinkGraphFoundationFrontierAcceptanceCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_cells(self) -> tuple[str, ...]:
        return tuple(f"{item.operation}:{item.expected_state}" for item in self.cells if not item.accepted)

    def for_operation(self, operation: str) -> tuple[LinkGraphFoundationFrontierAcceptanceCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "failed_cells": self.failed_cells, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_acceptance_matrix(evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierAcceptanceMatrix:
    cells = []
    for operation in LinkGraphFoundationFrontierOperation:
        rows = evaluation.by_operation(operation.value)
        for state in sorted({row.expected_state for row in rows}):
            selected = tuple(row for row in rows if row.expected_state == state)
            observed = sum(row.observed_state == state for row in selected)
            cells.append(LinkGraphFoundationFrontierAcceptanceCell(operation.value, state, observed, len(selected), observed == len(selected) and all(row.state_match and row.issue_match for row in selected), sum(row.role == "control" for row in selected)))
    values = tuple(cells)
    fixture_id = default_link_graph_foundation_frontier_fixture().fixture_id
    return LinkGraphFoundationFrontierAcceptanceMatrix(fixture_id, values, bool(values) and all(item.accepted for item in values))


def acceptance_matrix_summary(matrix: LinkGraphFoundationFrontierAcceptanceMatrix) -> dict[str, Any]:
    return {"fixture_id": matrix.fixture_id, "cell_count": len(matrix.cells), "passed_cells": sum(item.accepted for item in matrix.cells), "failed_cells": len(matrix.failed_cells), "operation_count": len({item.operation for item in matrix.cells}), "accepted": matrix.accepted}


__all__ = ["LinkGraphFoundationFrontierAcceptanceCell", "LinkGraphFoundationFrontierAcceptanceMatrix", "acceptance_matrix_summary", "build_link_graph_foundation_frontier_acceptance_matrix"]
