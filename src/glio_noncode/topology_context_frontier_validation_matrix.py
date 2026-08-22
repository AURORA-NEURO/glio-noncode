"""Validation matrix for operation, role, and expected state coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierValidationCell:
    cell_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierValidationReport:
    cells: tuple[TopologyContextFrontierValidationCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_validation_matrix(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierValidationReport:
    cells = tuple(
        TopologyContextFrontierValidationCell(
            f"cell-{item.record_id}",
            item.operation,
            item.role,
            item.expected_state,
            item.observed_state,
            item.state_match and item.issue_match,
        )
        for item in evaluation.rows
    )
    return TopologyContextFrontierValidationReport(cells, all(item.passed for item in cells))


def validate_topology_context_frontier_matrix(
    report: TopologyContextFrontierValidationReport,
) -> bool:
    return report.accepted and len(report.cells) == 16 and all(item.passed for item in report.cells)


__all__ = [
    "TopologyContextFrontierValidationCell",
    "TopologyContextFrontierValidationReport",
    "build_topology_context_frontier_validation_matrix",
    "validate_topology_context_frontier_matrix",
]
