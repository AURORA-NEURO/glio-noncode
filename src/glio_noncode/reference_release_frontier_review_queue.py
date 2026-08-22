"""Deterministic review queue for reference provenance and release controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_release import ReferenceReleaseManifest
from .reference_release_frontier_views import ReferenceReleaseReviewView
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReviewItem:
    """One queue item with a bounded review action."""

    queue_item_id: str
    record_id: str
    reason_codes: tuple[str, ...]
    priority: int
    action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseReviewQueue:
    """Stable queue ordered by descending priority and record ID."""

    queue_id: str
    release_address: str
    items: tuple[ReferenceReleaseReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"item_count": len(self.items)}


def build_reference_release_review_queue(
    view: ReferenceReleaseReviewView,
    manifest: ReferenceReleaseManifest,
    *,
    queue_id: str = "reference-release-frontier-review-queue",
) -> ReferenceReleaseReviewQueue:
    """Route blocked, drifted, and review rows without dropping controls."""

    require_non_empty(queue_id, "queue_id")
    selected = [
        row for row in view.rows if not row.accepted or row.state in {"review", "drift", "blocked"}
    ]
    items: list[ReferenceReleaseReviewItem] = []
    for row in selected:
        reasons = row.issue_codes or (f"state:{row.state}",)
        body = {
            "queue_item_id": f"queue-item:{row.record_id}",
            "record_id": row.record_id,
            "reason_codes": reasons,
            "priority": row.review_priority,
            "action": "inspect-source-receipts"
            if row.operation == "source_provenance_check"
            else "inspect-release-boundary",
        }
        items.append(
            ReferenceReleaseReviewItem(
                **body, content_address=content_hash(body, prefix="queue-item")
            )
        )
    ordered = tuple(sorted(items, key=lambda item: (-item.priority, item.record_id)))
    accepted = len(ordered) == len(selected) and all(
        item.content_address.startswith("queue-item:") for item in ordered
    )
    body = {
        "queue_id": queue_id,
        "release_address": manifest.content_address,
        "items": ordered,
        "accepted": accepted,
    }
    return ReferenceReleaseReviewQueue(
        **body, content_address=content_hash(body, prefix="review-queue")
    )


def verify_reference_release_review_queue(queue: ReferenceReleaseReviewQueue) -> tuple[str, ...]:
    """Return queue order, address, and reason closure failures."""

    failures: list[str] = []
    if not queue.accepted:
        failures.append("queue-not-accepted")
    if not queue.items:
        failures.append("queue-empty")
    if len({item.record_id for item in queue.items}) != len(queue.items):
        failures.append("queue-duplicates")
    if tuple(item.record_id for item in queue.items) != tuple(
        item.record_id
        for item in sorted(queue.items, key=lambda item: (-item.priority, item.record_id))
    ):
        failures.append("queue-order")
    if any(not item.reason_codes for item in queue.items):
        failures.append("queue-reason-missing")
    if any(not item.content_address.startswith("queue-item:") for item in queue.items):
        failures.append("queue-item-address")
    if not queue.content_address.startswith("review-queue:"):
        failures.append("queue-address")
    return tuple(failures)


__all__ = [
    "ReferenceReleaseReviewItem",
    "ReferenceReleaseReviewQueue",
    "build_reference_release_review_queue",
    "verify_reference_release_review_queue",
]
