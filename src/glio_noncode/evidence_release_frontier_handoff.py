"""Human-review handoff package with bounded claims and queue links."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseHandoff:
    fixture_id: str
    review_record_ids: tuple[str, ...]
    blocked_record_ids: tuple[str, ...]
    summary: dict[str, Any]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_handoff(fixture: Any, evaluation: Any, metrics: Any, queue: Any) -> EvidenceReleaseHandoff:
    review = tuple(item["record_id"] for item in queue.rows)
    blocked = tuple(item.record_id for item in evaluation.executions if item.observed_state.value == "blocked")
    summary = {"row_count": metrics.row_count, "state_counts": metrics.state_counts, "issue_counts": metrics.issue_counts, "review_count": len(review), "blocked_count": len(blocked)}
    body = {"fixture_id": fixture.fixture_id, "review_record_ids": review, "blocked_record_ids": blocked, "summary": summary, "accepted": bool(fixture.fixture_id)}
    return EvidenceReleaseHandoff(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseHandoff", "build_evidence_release_handoff"]
