"""Bounded review queue for Domain 14 lifecycle records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_policy import (
    EvidenceLifecycleDecision,
    EvidenceLifecyclePolicyDecision,
)
from .evidence_lifecycle_frontier_public_data import (
    EvidenceLifecycleFixture,
    EvidenceLifecycleOperation,
    EvidenceLifecycleRole,
)
from .serialization import content_hash, jsonable, require_non_empty


class EvidenceLifecycleReviewDisposition(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    HOLD_FOR_REPAIR = "hold_for_repair"


class EvidenceLifecycleReviewPriority(StrEnum):
    CITATION = "citation"
    GRAPH = "graph"
    EDGE = "edge"
    DISAGREEMENT = "disagreement"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReviewQueueItem:
    item_id: str
    record_id: str
    operation: EvidenceLifecycleOperation
    role: EvidenceLifecycleRole
    disposition: EvidenceLifecycleReviewDisposition
    priority: EvidenceLifecycleReviewPriority
    state: str
    issue_codes: tuple[str, ...]
    rationale: str
    next_action: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.disposition is EvidenceLifecycleReviewDisposition.READY_FOR_REVIEW

    @property
    def blocked(self) -> bool:
        return not self.accepted

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "blocked": self.blocked}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReviewQueueCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReviewQueue:
    queue_id: str
    fixture_id: str
    items: tuple[EvidenceLifecycleReviewQueueItem, ...]
    checks: tuple[EvidenceLifecycleReviewQueueCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(item.passed for item in self.checks)

    @property
    def ready_items(self) -> tuple[EvidenceLifecycleReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.accepted)

    @property
    def blocked_items(self) -> tuple[EvidenceLifecycleReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.blocked)

    def next_item(self) -> EvidenceLifecycleReviewQueueItem:
        rows = tuple(sorted(self.blocked_items or self.ready_items, key=lambda item: (item.priority.value, item.item_id)))
        return rows[0]

    def by_operation(self, operation: EvidenceLifecycleOperation) -> tuple[EvidenceLifecycleReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.operation is operation)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.items for code in item.issue_codes}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "ready_count": len(self.ready_items), "blocked_count": len(self.blocked_items), "next_item_id": self.next_item().item_id, "issue_codes": list(self.issue_codes())}


def _priority(operation: EvidenceLifecycleOperation, role: EvidenceLifecycleRole) -> EvidenceLifecycleReviewPriority:
    if role is EvidenceLifecycleRole.CONTROL:
        return EvidenceLifecycleReviewPriority.CONTROL
    return {EvidenceLifecycleOperation.CITATION_RESOLUTION: EvidenceLifecycleReviewPriority.CITATION, EvidenceLifecycleOperation.GRAPH_CONSTRUCTION: EvidenceLifecycleReviewPriority.GRAPH, EvidenceLifecycleOperation.EDGE_VALIDATION: EvidenceLifecycleReviewPriority.EDGE, EvidenceLifecycleOperation.DISAGREEMENT_TRACKING: EvidenceLifecycleReviewPriority.DISAGREEMENT}[operation]


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleReviewQueueCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return EvidenceLifecycleReviewQueueCheck(**body, content_address=content_hash(body))


def build_evidence_lifecycle_review_queue(fixture: EvidenceLifecycleFixture, evaluation: EvidenceLifecycleEvaluation, decisions: tuple[EvidenceLifecyclePolicyDecision, ...], *, queue_id: str = "evidence-lifecycle-review-queue") -> EvidenceLifecycleReviewQueue:
    require_non_empty(queue_id, "queue_id")
    decision_map = {item.operation: item for item in decisions}
    execution_map = evaluation.execution_map()
    items = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        decision = decision_map[record.operation]
        ready = record.role is EvidenceLifecycleRole.POSITIVE and execution.accepted and decision.decision is not EvidenceLifecycleDecision.BLOCK_RELEASE
        disposition = EvidenceLifecycleReviewDisposition.READY_FOR_REVIEW if ready else EvidenceLifecycleReviewDisposition.HOLD_FOR_REPAIR
        body = {"item_id": f"review:{record.record_id}", "record_id": record.record_id, "operation": record.operation, "role": record.role, "disposition": disposition, "priority": _priority(record.operation, record.role), "state": execution.state, "issue_codes": execution.issue_codes, "rationale": "positive lifecycle path satisfies the declared review policy" if ready else "control or failed lifecycle path retains a repair condition", "next_action": "route to bounded review" if ready else "resolve issue codes and replay"}
        items.append(EvidenceLifecycleReviewQueueItem(**body, content_address=content_hash(body)))
    item_ids = tuple(item.item_id for item in items)
    checks = (_check("queue:coverage", set(item.record_id for item in items) == set(execution_map), len(items), len(execution_map), "one item per execution"), _check("queue:positive-ready", sum(item.accepted for item in items if item.role is EvidenceLifecycleRole.POSITIVE) == 4, sum(item.accepted for item in items), 4, "positive rows are ready"), _check("queue:controls-held", all(item.blocked for item in items if item.role is EvidenceLifecycleRole.CONTROL), sum(item.blocked for item in items), 12, "control rows are held"), _check("queue:unique", len(item_ids) == len(set(item_ids)), len(item_ids), len(set(item_ids)), "item IDs are unique"), _check("queue:operations", {item.operation for item in items} == set(EvidenceLifecycleOperation), 4, 4, "four operations are represented"), _check("queue:fixture", fixture.fixture_id == evaluation.fixture_id, fixture.fixture_id, evaluation.fixture_id, "fixture identity is retained"))
    body = {"queue_id": queue_id, "fixture_id": fixture.fixture_id, "items": tuple(items), "checks": checks}
    return EvidenceLifecycleReviewQueue(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleReviewDisposition", "EvidenceLifecycleReviewPriority", "EvidenceLifecycleReviewQueue", "EvidenceLifecycleReviewQueueCheck", "EvidenceLifecycleReviewQueueItem", "build_evidence_lifecycle_review_queue"]
