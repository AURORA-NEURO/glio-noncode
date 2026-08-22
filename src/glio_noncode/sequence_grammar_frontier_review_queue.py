"""Addressable review queue for controls and unsupported grammar paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_views import (
    SequenceGrammarReviewEntry,
    SequenceGrammarView,
    filter_sequence_grammar_review_queue,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarQueueItem:
    queue_id: str
    ordinal: int
    entry: SequenceGrammarReviewEntry
    action: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id.strip() or self.ordinal < 1:
            raise ValidationError("queue item identity is invalid")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "queue_id": self.queue_id,
                        "ordinal": self.ordinal,
                        "entry": self.entry,
                        "action": self.action,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarReviewQueue:
    queue_id: str
    accepted: bool
    items: tuple[SequenceGrammarQueueItem, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id.strip() or not self.items:
            raise ValidationError("review queue requires identity and items")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"queue_id": self.queue_id, "accepted": self.accepted, "items": self.items}
                ),
            )

    def next_item(self) -> SequenceGrammarQueueItem:
        return self.items[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "accepted": self.accepted,
            "item_count": len(self.items),
            "items": [item.to_dict() for item in self.items],
            "content_address": self.content_address,
        }


def build_sequence_grammar_review_queue(
    view: SequenceGrammarView, *, queue_id: str = "sequence-grammar-review"
) -> SequenceGrammarReviewQueue:
    entries = filter_sequence_grammar_review_queue(view)
    items = tuple(
        SequenceGrammarQueueItem(queue_id, index, entry, entry.review_action)
        for index, entry in enumerate(entries, start=1)
    )
    return SequenceGrammarReviewQueue(queue_id, len(items) == view.review_count, items)


__all__ = [
    "SequenceGrammarQueueItem",
    "SequenceGrammarReviewQueue",
    "build_sequence_grammar_review_queue",
]
