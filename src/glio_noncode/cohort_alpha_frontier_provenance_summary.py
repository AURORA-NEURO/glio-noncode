"""Provenance summary grouped by operation and release partition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy, CohortAlphaFrontierProvenance
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierProvenanceSummaryRow:
    operation: str
    source_count: int
    result_count: int
    publish_count: int
    review_count: int
    quarantine_count: int
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierProvenanceSummary:
    rows: tuple[CohortAlphaFrontierProvenanceSummaryRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_provenance_summary(provenance: CohortAlphaFrontierProvenance, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierProvenanceSummary:
    rows = []
    for operation in ("C09", "C10", "C11", "C12"):
        decisions = tuple(item for item in policy.decisions if item.operation == operation)
        rows.append(CohortAlphaFrontierProvenanceSummaryRow(operation, len(provenance.source_ids), len(decisions), sum(item.disposition.value == "publish" for item in decisions), sum(item.disposition.value == "review" for item in decisions), sum(item.disposition.value == "quarantine" for item in decisions), provenance.closed, content_hash({"operation": operation, "source_count": len(provenance.source_ids), "results": len(decisions), "closed": provenance.closed}, prefix="alpha-provenance-summary")))
    values = tuple(rows)
    return CohortAlphaFrontierProvenanceSummary(values, provenance.closed and len(values) == 4 and all(item.result_count == 4 for item in values), content_hash(values, prefix="alpha-provenance-summary-report"))


__all__ = ["CohortAlphaFrontierProvenanceSummary", "CohortAlphaFrontierProvenanceSummaryRow", "build_cohort_alpha_frontier_provenance_summary"]
