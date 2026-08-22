"""Validation matrix over states, controls, and evidence methods."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierValidationCell:
    operation: str
    expected_state: str
    expected_issue: str
    rows: int
    state_matches: int
    issue_matches: int
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierValidationReport:
    fixture_id: str
    cells: tuple[LinkGraphBetaFrontierValidationCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_cells(self) -> tuple[str, ...]:
        return tuple(f"{item.operation}:{item.expected_state}:{item.expected_issue}" for item in self.cells if not item.accepted)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "failed_cells": self.failed_cells, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_validation_matrix(evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierValidationReport:
    cells = []
    for operation in LinkGraphBetaFrontierOperation:
        for row in evaluation.by_operation(operation.value):
            expected_issue = row.expected_issue_codes[0] if row.expected_issue_codes else "none"
            cells.append(LinkGraphBetaFrontierValidationCell(operation.value, row.expected_state, expected_issue, 1, int(row.state_match), int(row.issue_match), row.state_match and row.issue_match))
    values = tuple(cells)
    return LinkGraphBetaFrontierValidationReport(evaluation.fixture_id, values, bool(values) and all(item.accepted for item in values))


__all__ = ["LinkGraphBetaFrontierValidationCell", "LinkGraphBetaFrontierValidationReport", "build_link_graph_beta_frontier_validation_matrix"]
