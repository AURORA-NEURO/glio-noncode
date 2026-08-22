"""Deterministic review queue assembly for the Domain 13 planning frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_policy import (
    ValidationFrontierDecision,
    ValidationFrontierPolicyDecision,
)
from .validation_frontier_public_data import (
    ValidationFrontierFixture,
    ValidationFrontierOperation,
    ValidationFrontierRole,
)


class ValidationFrontierReviewDisposition(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    HOLD_FOR_REPAIR = "hold_for_repair"


class ValidationFrontierReviewPriority(StrEnum):
    ROUTING = "routing"
    DESIGN = "design"
    EVIDENCE = "evidence"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ValidationFrontierReviewQueueItem:
    item_id: str
    record_id: str
    operation: ValidationFrontierOperation
    role: ValidationFrontierRole
    disposition: ValidationFrontierReviewDisposition
    priority: ValidationFrontierReviewPriority
    state: str
    issue_codes: tuple[str, ...]
    rationale: str
    next_action: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("item_id", "record_id", "state", "rationale", "next_action"):
            require_non_empty(str(getattr(self, name)), name)

    @property
    def blocked(self) -> bool:
        return self.disposition is ValidationFrontierReviewDisposition.HOLD_FOR_REPAIR

    @property
    def accepted(self) -> bool:
        return self.disposition is ValidationFrontierReviewDisposition.READY_FOR_REVIEW

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"blocked": self.blocked, "accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class ValidationFrontierReviewQueueCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierReviewQueue:
    queue_id: str
    fixture_id: str
    items: tuple[ValidationFrontierReviewQueueItem, ...]
    checks: tuple[ValidationFrontierReviewQueueCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.queue_id, "queue_id")
        if not self.items:
            raise ValueError("validation review queue requires items")

    @property
    def accepted(self) -> bool:
        return all(item.passed for item in self.checks)

    @property
    def ready_items(self) -> tuple[ValidationFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.accepted)

    @property
    def blocked_items(self) -> tuple[ValidationFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.blocked)

    @property
    def positive_items(self) -> tuple[ValidationFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.role is ValidationFrontierRole.POSITIVE)

    @property
    def control_items(self) -> tuple[ValidationFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.role is ValidationFrontierRole.CONTROL)

    def by_operation(self, operation: ValidationFrontierOperation) -> tuple[ValidationFrontierReviewQueueItem, ...]:
        return tuple(item for item in self.items if item.operation is operation)

    def next_item(self) -> ValidationFrontierReviewQueueItem:
        ordered = tuple(sorted(self.blocked_items, key=lambda item: (item.priority.value, item.item_id)))
        if ordered:
            return ordered[0]
        return tuple(sorted(self.ready_items, key=lambda item: item.item_id))[0]

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.items for code in item.issue_codes}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "ready_count": len(self.ready_items),
            "blocked_count": len(self.blocked_items),
            "positive_count": len(self.positive_items),
            "control_count": len(self.control_items),
            "issue_codes": list(self.issue_codes()),
            "next_item_id": self.next_item().item_id,
        }


def _priority(operation: ValidationFrontierOperation, role: ValidationFrontierRole) -> ValidationFrontierReviewPriority:
    if role is ValidationFrontierRole.CONTROL:
        return ValidationFrontierReviewPriority.CONTROL
    if operation is ValidationFrontierOperation.EVIDENCE_GAP:
        return ValidationFrontierReviewPriority.EVIDENCE
    if operation is ValidationFrontierOperation.ASSAY_ELIGIBILITY:
        return ValidationFrontierReviewPriority.ROUTING
    return ValidationFrontierReviewPriority.DESIGN


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> ValidationFrontierReviewQueueCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return ValidationFrontierReviewQueueCheck(**body, content_address=content_hash(body))


def build_validation_frontier_review_queue(
    fixture: ValidationFrontierFixture,
    evaluation: ValidationFrontierEvaluation,
    decisions: tuple[ValidationFrontierPolicyDecision, ...],
    *,
    queue_id: str = "validation-frontier-review-queue",
) -> ValidationFrontierReviewQueue:
    require_non_empty(queue_id, "queue_id")
    decision_map = {item.operation: item for item in decisions}
    execution_map = evaluation.execution_map()
    items: list[ValidationFrontierReviewQueueItem] = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        decision = decision_map[record.operation]
        ready = record.role is ValidationFrontierRole.POSITIVE and execution.accepted and decision.decision is not ValidationFrontierDecision.BLOCK_RELEASE
        disposition = ValidationFrontierReviewDisposition.READY_FOR_REVIEW if ready else ValidationFrontierReviewDisposition.HOLD_FOR_REPAIR
        rationale = "positive execution satisfies the declared planning policy" if ready else "control or failed execution retains a blocking review condition"
        next_action = "route to bounded review" if ready else "resolve issue codes and replay"
        body = {"item_id": f"review:{record.record_id}", "record_id": record.record_id, "operation": record.operation, "role": record.role, "disposition": disposition, "priority": _priority(record.operation, record.role), "state": execution.state, "issue_codes": execution.issue_codes, "rationale": rationale, "next_action": next_action}
        items.append(ValidationFrontierReviewQueueItem(**body, content_address=content_hash(body)))
    item_ids = tuple(item.item_id for item in items)
    checks = (
        _check("queue:record-coverage", set(item.record_id for item in items) == set(execution_map), len(items), len(execution_map), "every execution has one queue item"),
        _check("queue:positive-policy", all(item.accepted for item in items if item.role is ValidationFrontierRole.POSITIVE), len(tuple(item for item in items if item.accepted)), 4, "positive records remain reviewable"),
        _check("queue:controls-held", all(item.blocked for item in items if item.role is ValidationFrontierRole.CONTROL), len(tuple(item for item in items if item.blocked)), 12, "control records remain held"),
        _check("queue:unique-items", len(item_ids) == len(set(item_ids)), len(item_ids), len(set(item_ids)), "queue item identifiers are unique"),
        _check("queue:operation-coverage", {item.operation for item in items} == set(ValidationFrontierOperation), len({item.operation for item in items}), 4, "all planning operations are represented"),
        _check("queue:fixture-binding", fixture.fixture_id == evaluation.fixture_id, fixture.fixture_id, evaluation.fixture_id, "queue binds the evaluated fixture"),
    )
    body = {"queue_id": queue_id, "fixture_id": fixture.fixture_id, "items": tuple(items), "checks": checks}
    return ValidationFrontierReviewQueue(**body, content_address=content_hash(body))


__all__ = [
    "ValidationFrontierReviewDisposition",
    "ValidationFrontierReviewPriority",
    "ValidationFrontierReviewQueue",
    "ValidationFrontierReviewQueueCheck",
    "ValidationFrontierReviewQueueItem",
    "build_validation_frontier_review_queue",
]
