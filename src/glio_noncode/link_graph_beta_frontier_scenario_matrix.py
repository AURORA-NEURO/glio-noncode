"""Scenario counts for beta-link positive and control behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierScenarioCell:
    operation: str
    role: str
    state: str
    record_ids: tuple[str, ...]
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierScenarioMatrix:
    fixture_id: str
    cells: tuple[LinkGraphBetaFrontierScenarioCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_cells(self) -> tuple[str, ...]:
        return tuple(f"{item.operation}:{item.role}:{item.state}" for item in self.cells if not item.accepted)

    def for_operation(self, operation: str) -> tuple[LinkGraphBetaFrontierScenarioCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "cells": [item.to_dict() for item in self.cells], "failed_cells": self.failed_cells, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_scenario_matrix(evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierScenarioMatrix:
    cells = []
    for operation in LinkGraphBetaFrontierOperation:
        rows = evaluation.by_operation(operation.value)
        for role in ("positive", "control"):
            selected = tuple(row for row in rows if row.role == role)
            for state in sorted({row.expected_state for row in selected}):
                values = tuple(row for row in selected if row.expected_state == state)
                cells.append(LinkGraphBetaFrontierScenarioCell(operation.value, role, state, tuple(row.record_id for row in values), all(row.state_match and row.issue_match for row in values)))
    values = tuple(cells)
    return LinkGraphBetaFrontierScenarioMatrix(evaluation.fixture_id, values, bool(values) and all(item.accepted for item in values))


__all__ = ["LinkGraphBetaFrontierScenarioCell", "LinkGraphBetaFrontierScenarioMatrix", "build_link_graph_beta_frontier_scenario_matrix"]
