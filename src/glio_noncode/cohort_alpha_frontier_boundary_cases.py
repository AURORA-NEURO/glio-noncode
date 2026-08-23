"""Boundary-case index for the four aggregate operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierBoundaryCase:
    case_id: str
    operation: str
    observed_state: str
    boundary_reason: str
    included_in_publish: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierBoundaryIndex:
    cases: tuple[CohortAlphaFrontierBoundaryCase, ...]
    case_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_boundary_index(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierBoundaryIndex:
    cases = []
    for row in evaluation.rows:
        if row.observed_state.value == "supported":
            continue
        reason = {"partial": "required channel absent", "ambiguous": "cohort direction disagrees", "out_of_domain": "foreign context", "abstained": "no observations"}[row.observed_state.value]
        cases.append(CohortAlphaFrontierBoundaryCase(row.record_id, row.operation, row.observed_state.value, reason, False, content_hash({"record_id": row.record_id, "operation": row.operation, "state": row.observed_state.value, "reason": reason}, prefix="alpha-boundary")))
    values = tuple(cases)
    return CohortAlphaFrontierBoundaryIndex(values, len(values), len(values) == 12 and all(not item.included_in_publish for item in values), content_hash(values, prefix="alpha-boundary-index"))


__all__ = ["CohortAlphaFrontierBoundaryCase", "CohortAlphaFrontierBoundaryIndex", "build_cohort_alpha_frontier_boundary_index"]
