"""Review queue construction with deterministic priority and routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_release import ChromatinContextFrontierReleaseManifest
from .chromatin_context_frontier_views import ChromatinContextFrontierReviewView
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierQueueItem:
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
            raise ValidationError("queue item is incomplete")
        if self.priority not in {"critical", "high", "normal", "advisory"}:
            raise ValidationError("queue priority is invalid")
        if self.status not in {"open", "accepted", "rejected", "deferred"}:
            raise ValidationError("queue status is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReviewQueue:
    queue_id: str
    items: tuple[ChromatinContextFrontierQueueItem, ...]
    accepted: bool
    blocking_count: int
    advisory_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id or not self.items:
            raise ValidationError("review queue is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def open_items(self) -> tuple[ChromatinContextFrontierQueueItem, ...]:
        return tuple(item for item in self.items if item.status == "open")

    def by_priority(self, priority: str) -> tuple[ChromatinContextFrontierQueueItem, ...]:
        return tuple(item for item in self.items if item.priority == priority)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"open_count": len(self.open_items)}


def build_chromatin_context_frontier_review_queue(
    view: ChromatinContextFrontierReviewView,
    release: ChromatinContextFrontierReleaseManifest,
    *,
    queue_id: str = "glio-noncode-d07-c01-c04-review",
) -> ChromatinContextFrontierReviewQueue:
    items: list[ChromatinContextFrontierQueueItem] = []
    for row in view.rows:
        if row.decision == "release":
            continue
        if row.observed_state == "out_of_domain":
            priority, route, reason, blocking = (
                "critical",
                "boundary",
                "foreign context requires refusal verification",
                True,
            )
        elif row.observed_state == "ambiguous":
            priority, route, reason, blocking = (
                "high",
                "replicate_review",
                "replicate spread requires adjudication",
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
                "required measurement is absent",
                False,
            )
        else:
            priority, route, reason, blocking = (
                "advisory",
                "manual_review",
                "state needs a manual check",
                False,
            )
        items.append(
            ChromatinContextFrontierQueueItem(
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
    return ChromatinContextFrontierReviewQueue(
        queue_id, ordered, accepted, blocking_count, advisory_count
    )


__all__ = [
    "ChromatinContextFrontierQueueItem",
    "ChromatinContextFrontierReviewQueue",
    "build_chromatin_context_frontier_review_queue",
]
