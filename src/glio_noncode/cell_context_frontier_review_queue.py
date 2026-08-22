"""Prioritized review queue for ambiguity, conflict, missingness, and refusal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_release import CellContextFrontierReleaseManifest
from .cell_context_frontier_views import CellContextFrontierReviewView
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierQueueItem:
    queue_item_id: str
    record_id: str
    operation: str
    observed_state: str
    priority: str
    route: str
    reason: str
    issue_codes: tuple[str, ...]
    blocking: bool
    status: str = "open"
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_item_id or not self.record_id or not self.reason:
            raise ValidationError("cell queue item is incomplete")
        if self.priority not in {"critical", "high", "normal", "advisory"}:
            raise ValidationError("cell queue priority is invalid")
        if self.status not in {"open", "accepted", "rejected", "deferred"}:
            raise ValidationError("cell queue status is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierReviewQueue:
    queue_id: str
    items: tuple[CellContextFrontierQueueItem, ...]
    accepted: bool
    blocking_count: int
    advisory_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id or not self.items:
            raise ValidationError("cell review queue is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def open_items(self) -> tuple[CellContextFrontierQueueItem, ...]:
        return tuple(item for item in self.items if item.status == "open")

    def by_route(self, route: str) -> tuple[CellContextFrontierQueueItem, ...]:
        return tuple(item for item in self.items if item.route == route)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"open_count": len(self.open_items)}


def build_cell_context_frontier_review_queue(
    view: CellContextFrontierReviewView,
    release: CellContextFrontierReleaseManifest,
    *,
    queue_id: str = "glio-noncode-d08-c01-c04-review",
) -> CellContextFrontierReviewQueue:
    items = []
    for row in view.rows:
        if row.decision == "release":
            continue
        if row.observed_state == "out_of_domain":
            priority, route, reason, blocking = (
                "critical",
                "context_boundary",
                "foreign context requires refusal verification",
                True,
            )
        elif row.observed_state == "contradictory":
            priority, route, reason, blocking = (
                "critical",
                "conflict_review",
                "declared context conflicts with taxonomy evidence",
                True,
            )
        elif row.observed_state == "ambiguous":
            priority, route, reason, blocking = (
                "high",
                "candidate_review",
                "multiple context candidates remain",
                True,
            )
        elif row.observed_state == "partial":
            priority, route, reason, blocking = (
                "high",
                "schema_review",
                "malformed input was quarantined",
                True,
            )
        elif row.observed_state == "abstained":
            priority, route, reason, blocking = (
                "normal",
                "missingness_review",
                "required dimension lacks support",
                False,
            )
        else:
            priority, route, reason, blocking = (
                "advisory",
                "context_review",
                "context row needs a manual check",
                False,
            )
        items.append(
            CellContextFrontierQueueItem(
                f"{queue_id}:{row.record_id}",
                row.record_id,
                row.operation,
                row.observed_state,
                priority,
                route,
                reason,
                row.issue_codes,
                blocking,
            )
        )
    order = {"critical": 0, "high": 1, "normal": 2, "advisory": 3}
    ordered = tuple(sorted(items, key=lambda item: (order[item.priority], item.record_id)))
    blocking_count = sum(item.blocking for item in ordered)
    advisory_count = sum(not item.blocking for item in ordered)
    accepted = (
        release.accepted and len(ordered) >= 8 and blocking_count >= 1 and advisory_count >= 1
    )
    return CellContextFrontierReviewQueue(
        queue_id, ordered, accepted, blocking_count, advisory_count
    )


__all__ = [
    "CellContextFrontierQueueItem",
    "CellContextFrontierReviewQueue",
    "build_cell_context_frontier_review_queue",
]
