"""Prioritized review queue for uncertain or bounded methylation rows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any

from .errors import ValidationError
from .methylation_frontier_release import MethylationFrontierReleaseManifest
from .methylation_frontier_views import MethylationFrontierReviewView
from .serialization import content_hash, jsonable


class MethylationFrontierReviewPriority(IntEnum):
    BLOCKING = 1
    CONTEXT = 2
    ISSUE = 3
    INFORMATIONAL = 4


class MethylationFrontierReviewDisposition(StrEnum):
    REQUIRED = "required"
    ADVISORY = "advisory"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class MethylationFrontierReviewQueueCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("review queue check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierReviewQueueItem:
    queue_id: str
    row_id: str
    record_id: str
    priority: MethylationFrontierReviewPriority
    disposition: MethylationFrontierReviewDisposition
    reason: str
    issue_codes: tuple[str, ...]
    state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id or not self.row_id or not self.record_id or not self.reason:
            raise ValidationError("review queue item is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MethylationFrontierReviewQueue:
    queue_id: str
    items: tuple[MethylationFrontierReviewQueueItem, ...]
    checks: tuple[MethylationFrontierReviewQueueCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id or not self.checks:
            raise ValidationError("review queue requires identity and checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def blocking_items(self) -> tuple[MethylationFrontierReviewQueueItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.priority is MethylationFrontierReviewPriority.BLOCKING
        )

    @property
    def required_items(self) -> tuple[MethylationFrontierReviewQueueItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.disposition is MethylationFrontierReviewDisposition.REQUIRED
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "blocking_count": len(self.blocking_items),
            "required_count": len(self.required_items),
        }


def build_methylation_frontier_review_queue(
    view: MethylationFrontierReviewView,
    release: MethylationFrontierReleaseManifest,
    *,
    queue_id: str = "methylation-frontier-review",
) -> MethylationFrontierReviewQueue:
    """Route context failures before data issues, preserving every reason."""

    items: list[MethylationFrontierReviewQueueItem] = []
    for row in view.rows:
        if row.decision == "release":
            continue
        if row.state == "out_of_domain":
            priority = MethylationFrontierReviewPriority.CONTEXT
            disposition = MethylationFrontierReviewDisposition.REQUIRED
            reason = "context or coordinate support is outside the declared boundary"
        elif row.state in {"invalid", "ambiguous"}:
            priority = MethylationFrontierReviewPriority.BLOCKING
            disposition = MethylationFrontierReviewDisposition.REQUIRED
            reason = "invalid or ambiguous evidence must be resolved before reuse"
        elif row.issue_codes:
            priority = MethylationFrontierReviewPriority.ISSUE
            disposition = MethylationFrontierReviewDisposition.REQUIRED
            reason = "retained issue codes require explicit review"
        elif row.decision != "release":
            priority = MethylationFrontierReviewPriority.INFORMATIONAL
            disposition = MethylationFrontierReviewDisposition.ADVISORY
            reason = "policy keeps this row visible for review"
        else:
            continue
        body = {
            "queue_id": queue_id,
            "row_id": row.row_id,
            "record_id": row.record_id,
            "priority": priority,
            "disposition": disposition,
            "reason": reason,
            "issue_codes": row.issue_codes,
            "state": row.state,
        }
        items.append(MethylationFrontierReviewQueueItem(**body))
    ordered = tuple(sorted(items, key=lambda item: (item.priority, item.record_id)))
    checks = (
        MethylationFrontierReviewQueueCheck(
            "queue_addresses",
            all(item.content_address.startswith("sha256:") for item in ordered),
            len(ordered),
            "all queued rows",
            "queued rows have content addresses",
        ),
        MethylationFrontierReviewQueueCheck(
            "release_state_visible",
            bool(view.release_state and release.release_id),
            view.release_state,
            "release state",
            "release state is retained through the view",
        ),
        MethylationFrontierReviewQueueCheck(
            "context_first",
            all(
                ordered[index].priority <= ordered[index + 1].priority
                for index in range(len(ordered) - 1)
            ),
            [item.priority for item in ordered],
            "ascending priority",
            "queue ordering is deterministic",
        ),
    )
    return MethylationFrontierReviewQueue(
        queue_id, ordered, checks, all(check.passed for check in checks)
    )


__all__ = [
    "MethylationFrontierReviewDisposition",
    "MethylationFrontierReviewPriority",
    "MethylationFrontierReviewQueue",
    "MethylationFrontierReviewQueueCheck",
    "MethylationFrontierReviewQueueItem",
    "build_methylation_frontier_review_queue",
]
