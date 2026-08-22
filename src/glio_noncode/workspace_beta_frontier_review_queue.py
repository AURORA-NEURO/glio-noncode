"""Priority review queue for unresolved projection cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_public_data import BetaFrontierOperation
from .workspace_beta_frontier_release import BetaFrontierReleaseManifest
from .workspace_beta_frontier_views import BetaFrontierReviewView


class BetaFrontierReviewPriority(IntEnum):
    BLOCKING = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class BetaFrontierReviewDisposition(StrEnum):
    QUEUED = "queued"
    RESOLVED = "resolved"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class BetaFrontierReviewQueueCheck:
    """Queue invariant and its observed value."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierReviewQueueItem:
    """One actionable review task."""

    item_id: str
    record_id: str
    operation: BetaFrontierOperation
    priority: BetaFrontierReviewPriority
    disposition: BetaFrontierReviewDisposition
    state: str
    decision: str
    issue_codes: tuple[str, ...]
    action: str
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.item_id, "item_id")
        require_non_empty(self.action, "action")
        require_non_empty(self.rationale, "rationale")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierReviewQueue:
    """Ordered queue plus invariant checks."""

    fixture_id: str
    items: tuple[BetaFrontierReviewQueueItem, ...]
    checks: tuple[BetaFrontierReviewQueueCheck, ...]
    ready_count: int
    held_count: int
    content_address: str

    def blocking_items(self) -> tuple[BetaFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.priority == BetaFrontierReviewPriority.BLOCKING)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _priority(row: Any) -> BetaFrontierReviewPriority:
    if row.state in {"invalid", "contradictory", "out_of_domain"}:
        return BetaFrontierReviewPriority.BLOCKING
    if row.state in {"partial", "incomplete"}:
        return BetaFrontierReviewPriority.HIGH
    if row.decision == "abstain":
        return BetaFrontierReviewPriority.NORMAL
    return BetaFrontierReviewPriority.LOW


def build_beta_frontier_review_queue(fixture: Any, evaluation: Any, decisions: Any, view: BetaFrontierReviewView, release: BetaFrontierReleaseManifest) -> BetaFrontierReviewQueue:
    """Create one queue item per held or abstaining review row."""

    items: list[BetaFrontierReviewQueueItem] = []
    for row in view.rows:
        if row.decision == "ready":
            continue
        priority = _priority(row)
        action = "verify context and receipts" if "context_mismatch" in row.issue_codes else "review unresolved projection state"
        rationale = "release is held until this row is reconciled" if release.state.value == "held" else "row remains visible for research review"
        body = {"item_id": f"queue:{row.record_id}", "record_id": row.record_id, "operation": BetaFrontierOperation(row.operation), "priority": priority, "disposition": BetaFrontierReviewDisposition.QUEUED, "state": row.state, "decision": row.decision, "issue_codes": row.issue_codes, "action": action, "rationale": rationale}
        items.append(BetaFrontierReviewQueueItem(**body, content_address=content_hash(body)))
    items.sort(key=lambda item: (item.priority, item.operation.value, item.record_id))
    checks_body = (
        ("queue:held-visible", all(item.decision != "ready" for item in view.rows if item.decision != "ready"), "every non-ready row can be reviewed"),
        ("queue:operation-coverage", len({item.operation for item in items}) >= 3, "held rows cover multiple surfaces"),
        ("queue:addresses", all(item.content_address.startswith("sha256:") for item in items), "queue items are addressed"),
        ("queue:release-link", bool(release.content_address), "queue retains release linkage"),
    )
    checks = tuple(
        BetaFrontierReviewQueueCheck(check_id=check_id, passed=passed, detail=detail, content_address=content_hash((check_id, passed, detail)))
        for check_id, passed, detail in checks_body
    )
    body = {"fixture_id": fixture.fixture_id, "items": tuple(items), "checks": checks, "ready_count": view.ready_count, "held_count": view.held_count}
    return BetaFrontierReviewQueue(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierReviewDisposition", "BetaFrontierReviewPriority", "BetaFrontierReviewQueue", "BetaFrontierReviewQueueCheck", "BetaFrontierReviewQueueItem", "build_beta_frontier_review_queue"]
