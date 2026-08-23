"""Priority scoring for the bounded review queue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPriorityRow:
    record_id: str
    operation: str
    base_priority: int
    evidence_gap_count: int
    score: int
    escalation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierPriorityReport:
    rows: tuple[CohortAlphaFrontierPriorityRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_review_priority(queue: CohortAlphaFrontierReviewQueue) -> CohortAlphaFrontierPriorityReport:
    rows = tuple(CohortAlphaFrontierPriorityRow(item.record_id, item.operation, item.priority, len(item.required_evidence), item.priority * 10 + len(item.required_evidence), "source review" if item.priority == 1 else "cohort review", content_hash({"record_id": item.record_id, "operation": item.operation, "priority": item.priority, "gap_count": len(item.required_evidence)}, prefix="alpha-priority")) for item in queue.items)
    return CohortAlphaFrontierPriorityReport(rows, queue.accepted and len(rows) == 12 and all(item.score > 0 for item in rows), content_hash(rows, prefix="alpha-priority-report"))


__all__ = ["CohortAlphaFrontierPriorityReport", "CohortAlphaFrontierPriorityRow", "build_cohort_alpha_frontier_review_priority"]
