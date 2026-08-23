"""Review notes generated from explicit state boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewNote:
    record_id: str
    operation: str
    note: str
    evidence_request: str
    blocking: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewNotes:
    notes: tuple[CohortAlphaFrontierReviewNote, ...]
    blocking_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_review_notes(queue: CohortAlphaFrontierReviewQueue) -> CohortAlphaFrontierReviewNotes:
    notes = tuple(CohortAlphaFrontierReviewNote(item.record_id, item.operation, item.reason, ", ".join(item.required_evidence), item.priority == 1, content_hash({"record_id": item.record_id, "operation": item.operation, "reason": item.reason, "evidence": item.required_evidence, "blocking": item.priority == 1}, prefix="alpha-review-note")) for item in queue.items)
    return CohortAlphaFrontierReviewNotes(notes, sum(item.blocking for item in notes), queue.accepted and len(notes) == 12 and all(item.evidence_request for item in notes), content_hash(notes, prefix="alpha-review-notes"))


__all__ = ["CohortAlphaFrontierReviewNote", "CohortAlphaFrontierReviewNotes", "build_cohort_alpha_frontier_review_notes"]
