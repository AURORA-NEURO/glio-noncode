"""Evidence-method matrix across the four link operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierEvidenceCell:
    operation: str
    evidence_kind: str
    record_ids: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_codes: tuple[str, ...]
    coverage: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierEvidenceMatrix:
    cells: tuple[LinkGraphAlphaFrontierEvidenceCell, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[LinkGraphAlphaFrontierEvidenceCell, ...]:
        return tuple(item for item in self.cells if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_evidence_matrix(evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierEvidenceMatrix:
    cells = []
    for row in evaluation.rows:
        kinds = row.adapter.measurements.get("assay_kinds") or row.adapter.measurements.get("states") or (row.operation,)
        for kind in kinds:
            cells.append(LinkGraphAlphaFrontierEvidenceCell(row.operation, str(kind), (row.record_id,), (row.observed_state,), row.observed_issue_codes, "observed"))
    values = tuple(cells)
    checks = (check("cells_present", bool(values), "method cells are populated"), check("record_coverage", {record for item in values for record in item.record_ids} == {row.record_id for row in evaluation.rows}, "every replay row maps to a method cell"), check("issue_retention", all(item.issue_codes or item.state_values == ("supported",) for item in values), "non-clean cells carry issue context"))
    return LinkGraphAlphaFrontierEvidenceMatrix(values, checks, all(item.passed for item in checks))


def summarize_link_graph_alpha_frontier_evidence_matrix(matrix: LinkGraphAlphaFrontierEvidenceMatrix) -> dict[str, Any]:
    return {"cell_count": len(matrix.cells), "operations": sorted({item.operation for item in matrix.cells}), "evidence_kinds": sorted({item.evidence_kind for item in matrix.cells}), "accepted": matrix.accepted}


__all__ = ["LinkGraphAlphaFrontierEvidenceCell", "LinkGraphAlphaFrontierEvidenceMatrix", "build_link_graph_alpha_frontier_evidence_matrix", "summarize_link_graph_alpha_frontier_evidence_matrix"]
