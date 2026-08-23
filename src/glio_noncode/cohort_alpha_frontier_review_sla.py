"""Review service levels for partial, ambiguous, and quarantined paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewSla:
    priority: int
    disposition: str
    target_days: int
    escalation: str
    required_evidence: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewSlaReport:
    rules: tuple[CohortAlphaFrontierReviewSla, ...]
    queue_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_review_sla(queue: CohortAlphaFrontierReviewQueue) -> CohortAlphaFrontierReviewSlaReport:
    raw = ((1, "quarantine", 2, "escalate to source owner", ("context receipt", "source receipt")), (2, "review", 7, "escalate to cohort reviewer", ("phase receipt", "direction receipt")))
    rules = tuple(CohortAlphaFrontierReviewSla(priority, disposition, days, escalation, evidence, content_hash({"priority": priority, "disposition": disposition, "days": days, "escalation": escalation, "evidence": evidence}, prefix="alpha-review-sla")) for priority, disposition, days, escalation, evidence in raw)
    return CohortAlphaFrontierReviewSlaReport(rules, queue.open_count, queue.accepted and len(rules) == 2 and all(item.target_days > 0 for item in rules), content_hash({"rules": rules, "queue": queue.content_address}, prefix="alpha-review-sla-report"))


__all__ = ["CohortAlphaFrontierReviewSla", "CohortAlphaFrontierReviewSlaReport", "build_cohort_alpha_frontier_review_sla"]
