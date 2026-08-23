"""Release summary joining publication counts with limitation text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleaseSummary:
    release_id: str
    total_rows: int
    publishable_rows: int
    review_rows: int
    quarantine_rows: int
    limitation: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_release_summary(metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierReleaseSummary:
    limitation = "descriptive aggregate evidence only; no causal, prognostic, or clinical claim"
    body = {"release": "cohort-alpha-frontier-c09-c12", "total": metrics.total_rows, "publish": policy.publishable_count, "review": policy.review_count, "quarantine": policy.quarantine_count, "limitation": limitation}
    return CohortAlphaFrontierReleaseSummary(body["release"], metrics.total_rows, policy.publishable_count, policy.review_count, policy.quarantine_count, limitation, metrics.total_rows == 16 and policy.publishable_count == 4 and policy.review_count == 4 and policy.quarantine_count == 8, content_hash(body, prefix="alpha-release-summary"))


__all__ = ["CohortAlphaFrontierReleaseSummary", "build_cohort_alpha_frontier_release_summary"]
