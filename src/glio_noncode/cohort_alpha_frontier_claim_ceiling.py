"""Claim-ceiling receipt attached to every sanitized release payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_publication_filter import CohortAlphaFrontierPublicationFilter
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimCeiling:
    ceiling_id: str
    allowed_scope: str
    blocked_scope: tuple[str, ...]
    eligible_count: int
    attached: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_claim_ceiling(filter_result: CohortAlphaFrontierPublicationFilter) -> CohortAlphaFrontierClaimCeiling:
    blocked = ("causation", "prognosis", "treatment recommendation", "clinical validity", "transportability", "significance")
    allowed = "descriptive exact-context aggregate evidence"
    body = {"id": "cohort-alpha-frontier-claim-ceiling", "allowed": allowed, "blocked": blocked, "eligible": filter_result.eligible_count, "attached": filter_result.accepted}
    return CohortAlphaFrontierClaimCeiling(body["id"], allowed, blocked, filter_result.eligible_count, filter_result.accepted, content_hash(body, prefix="alpha-claim-ceiling"))


__all__ = ["CohortAlphaFrontierClaimCeiling", "build_cohort_alpha_frontier_claim_ceiling"]
