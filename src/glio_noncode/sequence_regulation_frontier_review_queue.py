"""Review queue derived from partial, invalid, and boundary paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_views import SequenceRegulationView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationReviewItem:
    queue_id: str
    record_id: str
    priority: str
    reason: str
    state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.queue_id
            or not self.record_id
            or self.priority not in {"high", "normal", "low"}
        ):
            raise ValidationError("review item is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationReviewQueue:
    items: tuple[SequenceRegulationReviewItem, ...]
    accepted: bool
    high_priority_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_review_queue(
    view: SequenceRegulationView,
) -> SequenceRegulationReviewQueue:
    items = tuple(
        SequenceRegulationReviewItem(
            queue_id=f"review:{row.record_id}",
            record_id=row.record_id,
            priority="high" if row.state in {"invalid", "out_of_domain"} else "normal",
            reason="; ".join(row.issue_codes) or "partial evidence requires visible review",
            state=row.state,
        )
        for row in view.rows
        if not row.release_allowed
    )
    return SequenceRegulationReviewQueue(
        items, view.accepted, sum(item.priority == "high" for item in items)
    )


__all__ = [
    "SequenceRegulationReviewItem",
    "SequenceRegulationReviewQueue",
    "build_sequence_regulation_review_queue",
]
