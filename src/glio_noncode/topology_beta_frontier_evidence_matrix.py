"""Evidence matrix across operations, roles, states, and review obligations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierEvidenceCell:
    cell_id: str
    operation: str
    role: str
    state: str
    record_ids: tuple[str, ...]
    source_count: int
    evidence_count: int
    issue_codes: tuple[str, ...]
    review_required: bool
    payload_complete: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierEvidenceMatrix:
    cells: tuple[TopologyBetaFrontierEvidenceCell, ...]
    operation_count: int
    record_count: int
    review_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyBetaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def for_state(self, state: str) -> tuple[TopologyBetaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "operation_count": self.operation_count, "record_count": self.record_count, "review_count": self.review_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_evidence_matrix(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierEvidenceMatrix:
    cells = []
    for index, row in enumerate(evaluation.rows, start=1):
        cells.append(TopologyBetaFrontierEvidenceCell(f"cell-{index:02d}", row.operation, row.role, row.observed_state, (row.record_id,), len(row.adapter.source_ids), len(row.adapter.evidence_ids), row.observed_issue_codes, row.role == "control" or row.observed_state != "supported", bool(row.adapter.measurements) and bool(row.adapter.content_address), "one replay row maps to one evidence cell"))
    values = tuple(cells)
    return TopologyBetaFrontierEvidenceMatrix(values, len({item.operation for item in values}), len(values), sum(item.review_required for item in values), len(values) == 16 and all(item.payload_complete for item in values))


def summarize_topology_beta_frontier_evidence_matrix(matrix: TopologyBetaFrontierEvidenceMatrix) -> dict[str, Any]:
    return {"operation_count": matrix.operation_count, "record_count": matrix.record_count, "review_count": matrix.review_count, "accepted": matrix.accepted, "states": {state: len(matrix.for_state(state)) for state in sorted({item.state for item in matrix.cells})}, "operations": {operation: len(matrix.for_operation(operation)) for operation in sorted({item.operation for item in matrix.cells})}}


__all__ = ["TopologyBetaFrontierEvidenceCell", "TopologyBetaFrontierEvidenceMatrix", "build_topology_beta_frontier_evidence_matrix", "summarize_topology_beta_frontier_evidence_matrix"]
