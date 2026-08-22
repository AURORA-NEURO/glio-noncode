"""Prioritized review queue derived from policy and release evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_release import GammaFrontierReleaseManifest
from .workspace_gamma_frontier_views import GammaFrontierReviewView


class GammaFrontierReviewPriority(IntEnum):
    """Queue priority where one is the most urgent."""

    BLOCKING = 1
    CONTEXT = 2
    ISSUE = 3
    INFORMATIONAL = 4


class GammaFrontierReviewDisposition(StrEnum):
    """Current queue disposition."""

    REQUIRED = "required"
    ADVISORY = "advisory"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class GammaFrontierReviewQueueCheck:
    """One queue-level invariant."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierReviewQueueItem:
    """One row routed into human review."""

    queue_id: str
    row_id: str
    record_id: str
    priority: GammaFrontierReviewPriority
    disposition: GammaFrontierReviewDisposition
    reason: str
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierReviewQueue:
    """Sorted review queue and its integrity checks."""

    queue_id: str
    items: tuple[GammaFrontierReviewQueueItem, ...]
    checks: tuple[GammaFrontierReviewQueueCheck, ...]
    accepted: bool
    content_address: str

    @property
    def blocking_items(self) -> tuple[GammaFrontierReviewQueueItem, ...]:
        return tuple(
            item for item in self.items if item.priority is GammaFrontierReviewPriority.BLOCKING
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"blocking_count": len(self.blocking_items)}


def build_gamma_frontier_review_queue(
    view: GammaFrontierReviewView,
    release: GammaFrontierReleaseManifest,
    *,
    queue_id: str = "workspace-gamma-frontier-review",
) -> GammaFrontierReviewQueue:
    """Route issue rows, foreign contexts, and non-release decisions."""

    items: list[GammaFrontierReviewQueueItem] = []
    for row in view.rows:
        if row.state == "out_of_domain":
            priority, disposition, reason = (
                GammaFrontierReviewPriority.CONTEXT,
                GammaFrontierReviewDisposition.REQUIRED,
                "context mismatch requires quarantine review",
            )
        elif row.issue_codes:
            priority, disposition, reason = (
                GammaFrontierReviewPriority.ISSUE,
                GammaFrontierReviewDisposition.REQUIRED,
                "retained issue codes require review",
            )
        elif row.decision != "release":
            priority, disposition, reason = (
                GammaFrontierReviewPriority.INFORMATIONAL,
                GammaFrontierReviewDisposition.ADVISORY,
                "policy routes clean result to review",
            )
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
        }
        items.append(
            GammaFrontierReviewQueueItem(
                **body, content_address=content_hash(body, prefix="queue-item")
            )
        )
    ordered = tuple(sorted(items, key=lambda item: (item.priority, item.record_id)))
    checks_body = (
        {
            "check_id": "queue-row-addresses",
            "passed": all(":" in item.content_address for item in ordered),
            "observed": len(ordered),
            "required": "addressed rows",
            "detail": "every queued row has an address",
        },
        {
            "check_id": "release-state-visible",
            "passed": bool(release.state.value),
            "observed": release.state.value,
            "required": "release state",
            "detail": "queue retains release state through its input view",
        },
    )
    checks = tuple(
        GammaFrontierReviewQueueCheck(
            **item, content_address=content_hash(item, prefix="queue-check")
        )
        for item in checks_body
    )
    body = {
        "queue_id": queue_id,
        "items": ordered,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return GammaFrontierReviewQueue(**body, content_address=content_hash(body, prefix="queue"))


__all__ = [
    "GammaFrontierReviewDisposition",
    "GammaFrontierReviewPriority",
    "GammaFrontierReviewQueue",
    "GammaFrontierReviewQueueCheck",
    "GammaFrontierReviewQueueItem",
    "build_gamma_frontier_review_queue",
]
