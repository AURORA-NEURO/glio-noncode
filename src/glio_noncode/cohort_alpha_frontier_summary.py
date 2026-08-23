"""Compact summary cards for downstream release consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy, CohortAlphaFrontierQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSummaryCard:
    card_id: str
    label: str
    value: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSummary:
    cards: tuple[CohortAlphaFrontierSummaryCard, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_summary(metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy, quality: CohortAlphaFrontierQualityGate) -> CohortAlphaFrontierSummary:
    raw = (("rows", "Rows", str(metrics.total_rows), "bounded fixture rows"), ("supported", "Supported", str(metrics.supported_rows), "rows with exact supported state"), ("controls", "Controls", str(metrics.control_rows), "partial, ambiguous, foreign, or abstained paths"), ("publish", "Publish", str(policy.publishable_count), "paths within publication ceiling"), ("review", "Review", str(policy.review_count), "paths requiring evidence"), ("quality", "Quality", "pass" if quality.accepted else "block", "release gate result"))
    cards = tuple(CohortAlphaFrontierSummaryCard(card_id, label, value, detail, content_hash({"id": card_id, "label": label, "value": value, "detail": detail}, prefix="alpha-summary-card")) for card_id, label, value, detail in raw)
    return CohortAlphaFrontierSummary(cards, len(cards) == 6 and quality.accepted, content_hash(cards, prefix="alpha-summary"))


__all__ = ["CohortAlphaFrontierSummary", "CohortAlphaFrontierSummaryCard", "build_cohort_alpha_frontier_summary"]
