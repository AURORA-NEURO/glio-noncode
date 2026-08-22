"""Coverage matrix over beta operation, role, and outcome state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierCoverageCell:
    operation: str
    role: str
    state: str
    expected_count: int
    observed_count: int
    issue_count: int
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierCoverageMatrix:
    fixture_id: str
    cells: tuple[LinkGraphBetaFrontierCoverageCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_cells(self) -> tuple[str, ...]:
        return tuple(f"{item.operation}:{item.role}:{item.state}" for item in self.cells if not item.accepted)

    def for_operation(self, operation: str) -> tuple[LinkGraphBetaFrontierCoverageCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "failed_cells": self.failed_cells, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_coverage_matrix(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierCoverageMatrix:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    cells = []
    for operation in LinkGraphBetaFrontierOperation:
        for role in ("positive", "control"):
            records = tuple(record for record in value.operation_records(operation) if record.role.value == role)
            for state in sorted({record.expected_state for record in records}):
                expected = tuple(record for record in records if record.expected_state == state)
                observed = tuple(row for row in replay.by_operation(operation.value) if row.role == role and row.expected_state == state and row.observed_state == state)
                cells.append(LinkGraphBetaFrontierCoverageCell(operation.value, role, state, len(expected), len(observed), sum(len(row.observed_issue_codes) for row in observed), len(expected) == len(observed) and all(row.issue_match for row in observed)))
    values = tuple(cells)
    return LinkGraphBetaFrontierCoverageMatrix(value.fixture_id, values, bool(values) and all(item.accepted for item in values))


def coverage_matrix_summary(matrix: LinkGraphBetaFrontierCoverageMatrix) -> dict[str, Any]:
    return {"fixture_id": matrix.fixture_id, "cell_count": len(matrix.cells), "expected_count": sum(item.expected_count for item in matrix.cells), "observed_count": sum(item.observed_count for item in matrix.cells), "issue_count": sum(item.issue_count for item in matrix.cells), "accepted": matrix.accepted}


__all__ = ["LinkGraphBetaFrontierCoverageCell", "LinkGraphBetaFrontierCoverageMatrix", "build_link_graph_beta_frontier_coverage_matrix", "coverage_matrix_summary"]
