"""Acceptance count oracle for a release report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAcceptanceCounts:
    publishable: int
    review: int
    quarantine: int
    total: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def count_cohort_alpha_frontier_acceptance(policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierAcceptanceCounts:
    total = len(policy.decisions)
    accepted = policy.publishable_count == 4 and policy.review_count == 4 and policy.quarantine_count == 8 and total == 16
    body = {"publishable": policy.publishable_count, "review": policy.review_count, "quarantine": policy.quarantine_count, "total": total, "accepted": accepted}
    return CohortAlphaFrontierAcceptanceCounts(policy.publishable_count, policy.review_count, policy.quarantine_count, total, accepted, content_hash(body, prefix="alpha-acceptance-counts"))


__all__ = ["CohortAlphaFrontierAcceptanceCounts", "count_cohort_alpha_frontier_acceptance"]
