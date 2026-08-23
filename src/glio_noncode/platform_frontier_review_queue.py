"""Bounded review queue projection for platform controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierQueueItem:
    queue_id: str
    record_id: str
    priority: int
    reason_codes: tuple[str, ...]
    reviewer_role: str
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierReviewQueue:
    fixture_id: str
    items: tuple[PlatformFrontierQueueItem, ...]
    omitted_record_ids: tuple[str, ...]
    max_items: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_review_queue(evaluation: PlatformFrontierEvaluation, *, max_items: int = 12) -> PlatformFrontierReviewQueue:
    candidates = [item for item in evaluation.executions if item.role is PlatformFrontierRole.CONTROL or not item.accepted]
    ordered = sorted(candidates, key=lambda item: (0 if item.issue_codes else 1, item.record_id))
    selected, omitted = ordered[:max_items], ordered[max_items:]
    items = []
    for index, row in enumerate(selected, start=1):
        body = {"queue_id": f"platform-review-{index:03d}", "record_id": row.record_id, "priority": 1 if row.issue_codes else 2, "reason_codes": row.issue_codes or ("control_visibility",), "reviewer_role": "platform_reviewer", "source_ids": ()}
        items.append(PlatformFrontierQueueItem(**body, content_address=content_hash(body)))
    return PlatformFrontierReviewQueue(evaluation.fixture_id, tuple(items), tuple(item.record_id for item in omitted), max_items, len(items) <= max_items, content_hash(tuple(items)))


def filter_platform_frontier_review_queue(queue: PlatformFrontierReviewQueue, *, reason_code: str | None = None) -> tuple[PlatformFrontierQueueItem, ...]:
    if reason_code is None:
        return queue.items
    return tuple(item for item in queue.items if reason_code in item.reason_codes)


__all__ = ["PlatformFrontierQueueItem", "PlatformFrontierReviewQueue", "build_platform_frontier_review_queue", "filter_platform_frontier_review_queue"]
