"""Review queue for unresolved workspace states and source boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_policy import WorkspaceFrontierDecision, WorkspaceFrontierPolicyDecision
from .workspace_frontier_public_data import WorkspaceFrontierFixture
from .workspace_frontier_release import WorkspaceFrontierReleaseManifest
from .workspace_frontier_views import WorkspaceFrontierReviewView


class WorkspaceFrontierReviewPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WorkspaceFrontierReviewDisposition(StrEnum):
    READY = "ready"
    HOLD = "hold"
    WITHHOLD = "withhold"


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReviewQueueItem:
    item_id: str
    record_id: str
    operation: str
    priority: WorkspaceFrontierReviewPriority
    disposition: WorkspaceFrontierReviewDisposition
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReviewQueueCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReviewQueue:
    fixture_id: str
    items: tuple[WorkspaceFrontierReviewQueueItem, ...]
    checks: tuple[WorkspaceFrontierReviewQueueCheck, ...]
    accepted: bool
    content_address: str

    @property
    def ready_items(self) -> tuple[WorkspaceFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.disposition is WorkspaceFrontierReviewDisposition.READY)

    @property
    def held_items(self) -> tuple[WorkspaceFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.disposition is not WorkspaceFrontierReviewDisposition.READY)

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.items for code in item.issue_codes}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"ready_count": len(self.ready_items), "held_count": len(self.held_items), "issue_codes": list(self.issue_codes)}


def _item(record_id: str, operation: str, issues: tuple[str, ...], source_ids: tuple[str, ...], decision: WorkspaceFrontierDecision, role: str, state: str, rationale: str) -> WorkspaceFrontierReviewQueueItem:
    disposition = WorkspaceFrontierReviewDisposition.READY if decision is WorkspaceFrontierDecision.ALLOW_RESEARCH_VIEW else WorkspaceFrontierReviewDisposition.WITHHOLD if decision is WorkspaceFrontierDecision.WITHHOLD_OUT_OF_DOMAIN else WorkspaceFrontierReviewDisposition.HOLD
    priority = WorkspaceFrontierReviewPriority.HIGH if disposition is not WorkspaceFrontierReviewDisposition.READY else WorkspaceFrontierReviewPriority.LOW if role == "positive" and state == "supported" else WorkspaceFrontierReviewPriority.MEDIUM
    body = {"item_id": f"workspace-review:{record_id}", "record_id": record_id, "operation": operation, "priority": priority, "disposition": disposition, "issue_codes": issues, "source_ids": source_ids, "rationale": rationale}
    return WorkspaceFrontierReviewQueueItem(**body, content_address=content_hash(body))


def _check(check_id: str, passed: bool, observed: Any, required: Any) -> WorkspaceFrontierReviewQueueCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required}
    return WorkspaceFrontierReviewQueueCheck(**body, content_address=content_hash(body))


def build_workspace_frontier_review_queue(fixture: WorkspaceFrontierFixture, evaluation: WorkspaceFrontierEvaluation, decisions: tuple[WorkspaceFrontierPolicyDecision, ...], view: WorkspaceFrontierReviewView, release: WorkspaceFrontierReleaseManifest) -> WorkspaceFrontierReviewQueue:
    record_map = fixture.record_map()
    decision_map = {item.record_id: item for item in decisions}
    rows = {item.record_id: item for item in view.rows}
    items = tuple(
        _item(execution.record_id, execution.operation.value, execution.issue_codes, record_map[execution.record_id].source_ids, decision_map[execution.record_id].decision, execution.role.value, execution.state, rows[execution.record_id].notes)
        for execution in evaluation.executions
    )
    checks = (
        _check("row-count", len(items) == len(fixture.records), len(items), len(fixture.records)),
        _check("addressed", all(item.content_address.startswith("sha256:") for item in items), True, True),
        _check("release-reference", bool(release.release_id), release.release_id, "non-empty"),
        _check("ready-positive", len(tuple(item for item in items if item.disposition is WorkspaceFrontierReviewDisposition.READY)) == 3, len(tuple(item for item in items if item.disposition is WorkspaceFrontierReviewDisposition.READY)), 3),
        _check("out-of-domain-withheld", all(item.disposition is WorkspaceFrontierReviewDisposition.WITHHOLD for item in items if "context_mismatch" in item.issue_codes), True, True),
        _check("issue-union", len({code for item in items for code in item.issue_codes}) >= 6, len({code for item in items for code in item.issue_codes}), ">=6"),
    )
    body = {"fixture_id": fixture.fixture_id, "items": items, "checks": checks, "accepted": all(item.passed for item in checks)}
    return WorkspaceFrontierReviewQueue(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierReviewDisposition", "WorkspaceFrontierReviewPriority", "WorkspaceFrontierReviewQueue", "WorkspaceFrontierReviewQueueCheck", "WorkspaceFrontierReviewQueueItem", "build_workspace_frontier_review_queue"]
