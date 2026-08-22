"""Validation matrix that makes operation-by-state coverage inspectable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierValidationCell:
    operation: str
    role: str
    state: str
    record_ids: tuple[str, ...]
    count: int
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierValidationReport:
    cells: tuple[TopologyBetaFrontierValidationCell, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def cell(self, operation: str, role: str) -> TopologyBetaFrontierValidationCell:
        for item in self.cells:
            if item.operation == operation and item.role == role:
                return item
        raise KeyError((operation, role))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_validation_matrix(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierValidationReport:
    cells = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        for role in ("positive", "control"):
            rows = tuple(item for item in evaluation.rows if item.operation == operation and item.role == role)
            cells.append(TopologyBetaFrontierValidationCell(operation, role, rows[0].observed_state if len(rows) == 1 else "mixed", tuple(item.record_id for item in rows), len(rows), bool(rows) and all(item.state_match and item.issue_match for item in rows), "state and issue expectations are replayed"))
    values = tuple(cells)
    return TopologyBetaFrontierValidationReport(values, len(values) == 8 and all(item.passed for item in values))


def validate_topology_beta_frontier_matrix(report: TopologyBetaFrontierValidationReport) -> bool:
    return report.accepted and len(report.cells) == 8 and all(item.count > 0 for item in report.cells)


__all__ = ["TopologyBetaFrontierValidationCell", "TopologyBetaFrontierValidationReport", "build_topology_beta_frontier_validation_matrix", "validate_topology_beta_frontier_matrix"]
