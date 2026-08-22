"""Prioritized review queue for context-alpha controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierQueueItem:
    queue_id: str
    record_id: str
    priority: str
    reason: str
    state: str
    next_check: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReviewQueue:
    items: tuple[CellContextAlphaFrontierQueueItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"count": self.count}


def build_cell_context_alpha_frontier_review_queue(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierReviewQueue:
    items = []
    for index, row in enumerate(evaluation.records, 1):
        if row.observed_state == "supported":
            continue
        priority = "high" if row.observed_state == "out_of_domain" else "normal"
        next_check = (
            "verify-exact-context"
            if row.observed_state == "out_of_domain"
            else "inspect-score-or-issue"
        )
        items.append(
            CellContextAlphaFrontierQueueItem(
                f"alpha-review-{index:03d}",
                row.record_id,
                priority,
                row.adapter.detail,
                row.observed_state,
                next_check,
            )
        )
    return CellContextAlphaFrontierReviewQueue(tuple(items), evaluation.accepted)


__all__ = [
    "CellContextAlphaFrontierQueueItem",
    "CellContextAlphaFrontierReviewQueue",
    "build_cell_context_alpha_frontier_review_queue",
]
