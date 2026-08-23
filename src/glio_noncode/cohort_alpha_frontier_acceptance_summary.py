"""Acceptance summary for release handoff and status reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy, CohortAlphaFrontierQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAcceptanceSummary:
    accepted: bool
    quality_accepted: bool
    publishable_count: int
    review_count: int
    quarantine_count: int
    statement: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_acceptance_summary(policy: CohortAlphaFrontierPolicy, quality: CohortAlphaFrontierQualityGate) -> CohortAlphaFrontierAcceptanceSummary:
    statement = "accepted for bounded descriptive release" if quality.accepted else "blocked pending quality evidence"
    body = {"accepted": quality.accepted, "quality": quality.accepted, "publish": policy.publishable_count, "review": policy.review_count, "quarantine": policy.quarantine_count, "statement": statement}
    return CohortAlphaFrontierAcceptanceSummary(quality.accepted, quality.accepted, policy.publishable_count, policy.review_count, policy.quarantine_count, statement, content_hash(body, prefix="alpha-acceptance-summary"))


__all__ = ["CohortAlphaFrontierAcceptanceSummary", "build_cohort_alpha_frontier_acceptance_summary"]
