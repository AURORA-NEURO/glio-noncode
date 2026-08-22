"""Evidence matrix across alpha operations, states, controls, and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierEvidenceCell:
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
class TopologyAlphaFrontierEvidenceMatrix:
    cells: tuple[TopologyAlphaFrontierEvidenceCell, ...]
    operation_count: int
    record_count: int
    review_count: int
    supported_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def for_state(self, state: str) -> tuple[TopologyAlphaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.state == state)

    def review_cells(self) -> tuple[TopologyAlphaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.review_required)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "operation_count": self.operation_count, "record_count": self.record_count, "review_count": self.review_count, "supported_count": self.supported_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_evidence_matrix(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierEvidenceMatrix:
    cells = tuple(
        TopologyAlphaFrontierEvidenceCell(
            f"cell-{index:02d}",
            row.operation,
            row.role,
            row.observed_state,
            (row.record_id,),
            len(row.adapter.source_ids),
            len(row.adapter.evidence_ids),
            row.observed_issue_codes,
            row.role == "control" or row.observed_state != "supported",
            bool(row.adapter.measurements) and row.adapter.content_address.startswith("sha256:"),
            "one replay row retains one source-to-result evidence cell",
        )
        for index, row in enumerate(evaluation.rows, start=1)
    )
    return TopologyAlphaFrontierEvidenceMatrix(
        cells,
        len({item.operation for item in cells}),
        len(cells),
        sum(item.review_required for item in cells),
        sum(item.state == "supported" for item in cells),
        len(cells) == 16 and len({item.operation for item in cells}) == 4 and all(item.payload_complete for item in cells),
    )


def summarize_topology_alpha_frontier_evidence_matrix(matrix: TopologyAlphaFrontierEvidenceMatrix) -> dict[str, Any]:
    return {"operation_count": matrix.operation_count, "record_count": matrix.record_count, "review_count": matrix.review_count, "supported_count": matrix.supported_count, "accepted": matrix.accepted, "states": {state: len(matrix.for_state(state)) for state in sorted({item.state for item in matrix.cells})}, "operations": {operation: len(matrix.for_operation(operation)) for operation in sorted({item.operation for item in matrix.cells})}}


__all__ = ["TopologyAlphaFrontierEvidenceCell", "TopologyAlphaFrontierEvidenceMatrix", "build_topology_alpha_frontier_evidence_matrix", "summarize_topology_alpha_frontier_evidence_matrix"]
