"""Bounded review queue for sequence-effect controls and unresolved outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_views import (
    SequenceEffectReviewEntry,
    SequenceEffectView,
    filter_sequence_effect_review_queue,
)
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class SequenceEffectQueueItem:
    queue_id: str
    entry: SequenceEffectReviewEntry
    disposition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "entry": self.entry.to_dict(),
            "disposition": self.disposition,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class SequenceEffectReviewQueue:
    queue_id: str
    items: tuple[SequenceEffectQueueItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id.strip():
            raise ValueError("queue ID is required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"queue_id": self.queue_id, "items": self.items, "accepted": self.accepted}
                ),
            )

    def next_item(self) -> SequenceEffectQueueItem | None:
        return self.items[0] if self.items else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "accepted": self.accepted,
            "item_count": len(self.items),
            "items": [item.to_dict() for item in self.items],
            "next_record_id": self.next_item().entry.record_id if self.next_item() else None,
            "content_address": self.content_address,
        }


def build_sequence_effect_review_queue(
    view: SequenceEffectView, queue_id: str = "sequence-effect-review"
) -> SequenceEffectReviewQueue:
    rows = sorted(
        filter_sequence_effect_review_queue(view), key=lambda item: (-item.priority, item.record_id)
    )
    items = tuple(
        SequenceEffectQueueItem(
            queue_id,
            row,
            "withhold-until-repaired",
            content_hash(
                {
                    "queue_id": queue_id,
                    "record_id": row.record_id,
                    "priority": row.priority,
                    "action": row.action,
                }
            ),
        )
        for row in rows
    )
    return SequenceEffectReviewQueue(
        queue_id,
        items,
        all(item.entry.priority > 0 for item in items) and len(items) == view.review_count,
    )


__all__ = [
    "SequenceEffectQueueItem",
    "SequenceEffectReviewQueue",
    "build_sequence_effect_review_queue",
]
