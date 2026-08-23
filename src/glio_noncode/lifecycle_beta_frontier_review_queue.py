"""Priority review queue derived from explicit unresolved states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierQueueItem:
    queue_id: str
    record_id: str
    priority: float
    state: LifecycleBetaFrontierState
    reasons: tuple[str, ...]
    required_roles: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReviewQueue:
    fixture_id: str
    items: tuple[LifecycleBetaFrontierQueueItem, ...]
    omitted_record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_review_queue(evaluation: LifecycleBetaFrontierEvaluation, *, limit: int = 64) -> LifecycleBetaFrontierReviewQueue:
    if limit < 1:
        raise ValueError("review queue limit must be positive")
    weights = {LifecycleBetaFrontierState.CONTRADICTORY: 1.0, LifecycleBetaFrontierState.SPLIT_DECISION: 0.98, LifecycleBetaFrontierState.OUT_OF_DOMAIN: 0.95, LifecycleBetaFrontierState.PARTIAL: 0.88, LifecycleBetaFrontierState.REVIEW_REQUIRED: 0.82, LifecycleBetaFrontierState.ABSTAINED: 0.76}
    candidates = []
    for item in evaluation.executions:
        priority = weights.get(item.state, 0.35)
        if item.issue_codes:
            priority = min(1.0, priority + 0.03 * len(item.issue_codes))
        body = {"queue_id": content_hash({"record_id": item.record_id, "state": item.state}, prefix="queue"), "record_id": item.record_id, "priority": round(priority, 6), "state": item.state, "reasons": tuple(item.issue_codes) or ("routine research review",), "required_roles": ("domain_expert", "data_provenance") if priority >= 0.8 else ("data_provenance",)}
        candidates.append(LifecycleBetaFrontierQueueItem(**body, content_address=content_hash(body)))
    candidates.sort(key=lambda item: (-item.priority, item.record_id))
    selected = tuple(candidates[:limit])
    omitted = tuple(item.record_id for item in candidates[limit:])
    return LifecycleBetaFrontierReviewQueue(evaluation.fixture_id, selected, omitted, content_hash({"items": selected, "omitted": omitted}))


def lifecycle_beta_frontier_queue_summary(queue: LifecycleBetaFrontierReviewQueue) -> dict[str, Any]:
    return {"fixture_id": queue.fixture_id, "item_count": len(queue.items), "omitted_count": len(queue.omitted_record_ids), "top_priority": queue.items[0].priority if queue.items else None, "content_address": queue.content_address}


__all__ = ["LifecycleBetaFrontierQueueItem", "LifecycleBetaFrontierReviewQueue", "build_lifecycle_beta_frontier_review_queue", "lifecycle_beta_frontier_queue_summary"]
