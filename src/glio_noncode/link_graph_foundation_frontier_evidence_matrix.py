"""Method and issue coverage matrix for baseline evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierEvidenceCell:
    operation: str
    evidence_kind: str
    record_ids: tuple[str, ...]
    states: tuple[str, ...]
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierEvidenceMatrix:
    cells: tuple[LinkGraphFoundationFrontierEvidenceCell, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"cells": [item.to_dict() for item in self.cells], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_evidence_matrix(evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierEvidenceMatrix:
    cells = tuple(LinkGraphFoundationFrontierEvidenceCell(row.operation, str(kind), (row.record_id,), (row.observed_state,), row.observed_issue_codes) for row in evaluation.rows for kind in (row.adapter.measurements.get("methods") or row.adapter.measurements.get("reason") or row.operation,))
    checks = (check("cells", bool(cells), "evidence cells exist"), check("coverage", {record for cell in cells for record in cell.record_ids} == {row.record_id for row in evaluation.rows}, "all records map to cells"), check("method_identity", any("consensus" in cell.evidence_kind or cell.evidence_kind in {"contact", "coaccessibility"} for cell in cells), "method identity is retained"))
    return LinkGraphFoundationFrontierEvidenceMatrix(cells, checks, all(item.passed for item in checks))


def summarize_link_graph_foundation_frontier_evidence_matrix(matrix: LinkGraphFoundationFrontierEvidenceMatrix) -> dict[str, Any]:
    return {"cell_count": len(matrix.cells), "operations": sorted({item.operation for item in matrix.cells}), "evidence_kinds": sorted({item.evidence_kind for item in matrix.cells}), "accepted": matrix.accepted}


__all__ = ["LinkGraphFoundationFrontierEvidenceCell", "LinkGraphFoundationFrontierEvidenceMatrix", "build_link_graph_foundation_frontier_evidence_matrix", "summarize_link_graph_foundation_frontier_evidence_matrix"]
