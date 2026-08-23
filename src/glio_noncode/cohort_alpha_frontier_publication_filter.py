"""Final publication filter applied to sanitized rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierDisposition, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPublicationFilterRow:
    record_id: str
    operation: str
    eligible: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPublicationFilter:
    rows: tuple[CohortAlphaFrontierPublicationFilterRow, ...]
    eligible_count: int
    rejected_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def apply_cohort_alpha_frontier_publication_filter(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierPublicationFilter:
    rows = []
    for result in evaluation.rows:
        decision = policy.for_record(result.record_id)
        eligible = decision.disposition is CohortAlphaFrontierDisposition.PUBLISH and result.accepted
        reason = "supported exact-context row" if eligible else "policy disposition excludes publication"
        rows.append(CohortAlphaFrontierPublicationFilterRow(result.record_id, result.operation, eligible, reason, content_hash({"record_id": result.record_id, "operation": result.operation, "eligible": eligible, "reason": reason}, prefix="alpha-publication-filter")))
    values = tuple(rows)
    return CohortAlphaFrontierPublicationFilter(values, sum(item.eligible for item in values), sum(not item.eligible for item in values), len(values) == 16 and sum(item.eligible for item in values) == policy.publishable_count, content_hash(values, prefix="alpha-publication-filter-report"))


__all__ = ["CohortAlphaFrontierPublicationFilter", "CohortAlphaFrontierPublicationFilterRow", "apply_cohort_alpha_frontier_publication_filter"]
