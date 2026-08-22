"""Priority routing for chromatin-alpha review rows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any

from .chromatin_alpha_frontier_release import ChromatinAlphaFrontierReleaseManifest
from .chromatin_alpha_frontier_views import ChromatinAlphaFrontierReviewView
from .errors import ValidationError
from .serialization import content_hash, jsonable


class ChromatinAlphaFrontierReviewPriority(IntEnum):
    BLOCKING = 1
    CONTEXT = 2
    AMBIGUITY = 3
    ISSUE = 4
    INFORMATIONAL = 5


class ChromatinAlphaFrontierReviewDisposition(StrEnum):
    REQUIRED = "required"
    ADVISORY = "advisory"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReviewQueueCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("queue check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReviewQueueItem:
    queue_id: str
    row_id: str
    record_id: str
    priority: ChromatinAlphaFrontierReviewPriority
    disposition: ChromatinAlphaFrontierReviewDisposition
    reason: str
    issue_codes: tuple[str, ...]
    state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id or not self.row_id or not self.record_id or not self.reason:
            raise ValidationError("queue item is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReviewQueue:
    queue_id: str
    items: tuple[ChromatinAlphaFrontierReviewQueueItem, ...]
    checks: tuple[ChromatinAlphaFrontierReviewQueueCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.queue_id or not self.checks:
            raise ValidationError("review queue requires identity and checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def blocking_items(self) -> tuple[ChromatinAlphaFrontierReviewQueueItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.priority is ChromatinAlphaFrontierReviewPriority.BLOCKING
        )

    @property
    def required_items(self) -> tuple[ChromatinAlphaFrontierReviewQueueItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.disposition is ChromatinAlphaFrontierReviewDisposition.REQUIRED
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "blocking_count": len(self.blocking_items),
            "required_count": len(self.required_items),
        }


def build_chromatin_alpha_frontier_review_queue(
    view: ChromatinAlphaFrontierReviewView,
    release: ChromatinAlphaFrontierReleaseManifest,
    *,
    queue_id: str = "chromatin-alpha-frontier-review",
) -> ChromatinAlphaFrontierReviewQueue:
    items: list[ChromatinAlphaFrontierReviewQueueItem] = []
    for row in view.rows:
        if row.decision == "release":
            continue
        if row.state == "out_of_domain":
            priority, disposition, reason = (
                ChromatinAlphaFrontierReviewPriority.CONTEXT,
                ChromatinAlphaFrontierReviewDisposition.REQUIRED,
                "foreign context is quarantined",
            )
        elif row.state == "ambiguous":
            priority, disposition, reason = (
                ChromatinAlphaFrontierReviewPriority.AMBIGUITY,
                ChromatinAlphaFrontierReviewDisposition.REQUIRED,
                "mixed replicate or delta directions require review",
            )
        elif row.issue_codes:
            priority, disposition, reason = (
                ChromatinAlphaFrontierReviewPriority.ISSUE,
                ChromatinAlphaFrontierReviewDisposition.REQUIRED,
                "retained primitive issue requires review",
            )
        else:
            priority, disposition, reason = (
                ChromatinAlphaFrontierReviewPriority.INFORMATIONAL,
                ChromatinAlphaFrontierReviewDisposition.ADVISORY,
                "control path remains visible",
            )
        items.append(
            ChromatinAlphaFrontierReviewQueueItem(
                queue_id,
                row.row_id,
                row.record_id,
                priority,
                disposition,
                reason,
                row.issue_codes,
                row.state,
            )
        )
    ordered = tuple(sorted(items, key=lambda item: (item.priority, item.record_id)))
    checks = (
        ChromatinAlphaFrontierReviewQueueCheck(
            "queue_addresses",
            all(item.content_address.startswith("sha256:") for item in ordered),
            len(ordered),
            "all queued rows",
            "every queued row is addressed",
        ),
        ChromatinAlphaFrontierReviewQueueCheck(
            "release_visible",
            bool(view.release_state and release.release_id),
            view.release_state,
            "release state",
            "release state is retained",
        ),
        ChromatinAlphaFrontierReviewQueueCheck(
            "ordered",
            all(
                ordered[index].priority <= ordered[index + 1].priority
                for index in range(len(ordered) - 1)
            ),
            [item.priority for item in ordered],
            "ascending priority",
            "queue ordering is deterministic",
        ),
        ChromatinAlphaFrontierReviewQueueCheck(
            "review_balance",
            len(ordered) == view.review_count,
            len(ordered),
            view.review_count,
            "every non-release row is routed",
        ),
    )
    return ChromatinAlphaFrontierReviewQueue(
        queue_id, ordered, checks, all(check.passed for check in checks)
    )


def chromatin_alpha_frontier_review_budget(
    view: ChromatinAlphaFrontierReviewView,
    *,
    maximum_priority: int = 4,
) -> dict[str, Any]:
    eligible = tuple(
        row for row in view.rows if row.decision != "release" and row.state != "out_of_domain"
    )
    return {
        "maximum_priority": maximum_priority,
        "eligible_review_count": len(eligible),
        "review_count": view.review_count,
        "content_address": content_hash(
            {"eligible": [row.record_id for row in eligible], "maximum_priority": maximum_priority}
        ),
    }


__all__ = [
    "ChromatinAlphaFrontierReviewDisposition",
    "ChromatinAlphaFrontierReviewPriority",
    "ChromatinAlphaFrontierReviewQueue",
    "ChromatinAlphaFrontierReviewQueueCheck",
    "ChromatinAlphaFrontierReviewQueueItem",
    "build_chromatin_alpha_frontier_review_queue",
    "chromatin_alpha_frontier_review_budget",
]
