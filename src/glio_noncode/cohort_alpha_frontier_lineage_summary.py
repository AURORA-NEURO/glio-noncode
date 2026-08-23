"""Lineage summary by relation and operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierLineage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierLineageSummaryRow:
    operation: str
    source_to_input_edges: int
    input_to_result_edges: int
    total_edges: int
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierLineageSummary:
    rows: tuple[CohortAlphaFrontierLineageSummaryRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def summarize_cohort_alpha_frontier_lineage(lineage: CohortAlphaFrontierLineage) -> CohortAlphaFrontierLineageSummary:
    rows = []
    for operation in ("C09", "C10", "C11", "C12"):
        edges = tuple(edge for edge in lineage.edges if edge.operation == operation)
        source_edges = sum(edge.relation == "source_to_input" for edge in edges)
        result_edges = sum(edge.relation == "input_to_result" for edge in edges)
        rows.append(CohortAlphaFrontierLineageSummaryRow(operation, source_edges, result_edges, len(edges), lineage.closed, content_hash({"operation": operation, "source": source_edges, "result": result_edges, "closed": lineage.closed}, prefix="alpha-lineage-summary")))
    values = tuple(rows)
    return CohortAlphaFrontierLineageSummary(values, lineage.closed and len(values) == 4 and all(item.total_edges >= 8 for item in values), content_hash(values, prefix="alpha-lineage-summary-report"))


__all__ = ["CohortAlphaFrontierLineageSummary", "CohortAlphaFrontierLineageSummaryRow", "summarize_cohort_alpha_frontier_lineage"]
