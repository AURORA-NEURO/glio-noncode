"""Review service-level bands for platform queue items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_review_queue import PlatformFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierReviewSlaRow:
    record_id: str
    priority: int
    target_hours: int
    escalation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierReviewSla:
    rows: tuple[PlatformFrontierReviewSlaRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_review_sla(queue: PlatformFrontierReviewQueue) -> PlatformFrontierReviewSla:
    rows = []
    for item in queue.items:
        target = 4 if item.priority == 1 else 24
        body = {"record_id": item.record_id, "priority": item.priority, "target_hours": target, "escalation": "platform_owner" if item.priority == 1 else "queue_manager"}
        rows.append(PlatformFrontierReviewSlaRow(**body, content_address=content_hash(body)))
    return PlatformFrontierReviewSla(tuple(rows), all(item.target_hours > 0 for item in rows), content_hash(tuple(rows)))


__all__ = ["PlatformFrontierReviewSla", "PlatformFrontierReviewSlaRow", "build_platform_frontier_review_sla"]
