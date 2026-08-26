"""Typed review projections for the module workbench execution ledger."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_REVIEW_VERSION = "module-workbench-execution-review-v1"
MODULE_WORKBENCH_EXECUTION_REVIEW_BOUNDARY = "public_aggregate_module_workbench_execution_review"
MODULE_WORKBENCH_EXECUTION_REVIEW_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_MODULES = 200_000
MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_NEXT_TASKS = 32


class ModuleWorkbenchExecutionReviewState(StrEnum):
    """Review routing state for one module rollup."""

    ATTENTION = "attention"
    EVIDENCE_PENDING = "evidence_pending"
    READY = "ready"
    WAITING = "waiting"
    VERIFY = "verify"
    COMPLETE = "complete"
    SUPERSEDED = "superseded"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _percent(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if not 0.0 <= float(value) <= 100.0:
        raise ValidationError(f"{field} must be between zero and one hundred")


def _ratio(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if not 0.0 <= float(value) <= 1.0:
        raise ValidationError(f"{field} must be between zero and one")


def _ordered(values: tuple[str, ...], field: str, maximum: int) -> None:
    if len(values) > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(values)) != values or len(set(values)) != len(values):
        raise ValidationError(f"{field} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionReviewItem:
    """One module-level rollup for human review routing."""

    module_id: str
    family: str
    task_count: int
    planned_count: int
    ready_count: int
    in_progress_count: int
    blocked_count: int
    completed_count: int
    skipped_count: int
    superseded_count: int
    completion_percent: float
    evidence_coverage_percent: float
    highest_priority: int
    critical_task_count: int
    review_state: ModuleWorkbenchExecutionReviewState
    next_task_ids: tuple[str, ...]
    blocker_details: tuple[str, ...]
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.module_id, "module_id", 512)
        _text(self.family, "family", 256)
        for field in (
            "task_count",
            "planned_count",
            "ready_count",
            "in_progress_count",
            "blocked_count",
            "completed_count",
            "skipped_count",
            "superseded_count",
            "critical_task_count",
        ):
            _count(getattr(self, field), field)
        if (
            sum(
                (
                    self.planned_count,
                    self.ready_count,
                    self.in_progress_count,
                    self.blocked_count,
                    self.completed_count,
                    self.skipped_count,
                    self.superseded_count,
                )
            )
            != self.task_count
        ):
            raise ValidationError("review state counts do not conserve task_count")
        _percent(self.completion_percent, "completion_percent")
        _percent(self.evidence_coverage_percent, "evidence_coverage_percent")
        _count(self.highest_priority, "highest_priority")
        if self.highest_priority > 100:
            raise ValidationError("highest_priority exceeds 100")
        if not isinstance(self.review_state, ModuleWorkbenchExecutionReviewState):
            raise ValidationError("review_state must be supported")
        _ordered(
            self.next_task_ids, "next_task_ids", MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_NEXT_TASKS
        )
        _ordered(self.blocker_details, "blocker_details", 64)
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_review_item(
    value: ModuleWorkbenchExecutionReviewItem,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-review-item")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionReview:
    """Stable module review queue derived from the task-level ledger."""

    ledger_address: str
    items: tuple[ModuleWorkbenchExecutionReviewItem, ...]
    module_count: int
    attention_count: int
    evidence_pending_count: int
    ready_count: int
    waiting_count: int
    verify_count: int
    complete_count: int
    superseded_count: int
    next_task_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.ledger_address, "ledger_address")
        if len(self.items) > MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_MODULES:
            raise ValidationError("execution review module limit exceeded")
        ids = tuple(item.module_id for item in self.items)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("review items must be sorted and unique")
        _count(self.module_count, "module_count")
        if self.module_count != len(self.items):
            raise ValidationError("module_count does not conserve review items")
        for field in (
            "attention_count",
            "evidence_pending_count",
            "ready_count",
            "waiting_count",
            "verify_count",
            "complete_count",
            "superseded_count",
            "next_task_count",
        ):
            _count(getattr(self, field), field)
        if (
            sum(
                (
                    self.attention_count,
                    self.evidence_pending_count,
                    self.ready_count,
                    self.waiting_count,
                    self.verify_count,
                    self.complete_count,
                    self.superseded_count,
                )
            )
            != self.module_count
        ):
            raise ValidationError("review state counts do not conserve modules")
        if self.next_task_count != sum(len(item.next_task_ids) for item in self.items):
            raise ValidationError("next_task_count does not conserve routed tasks")
        if not isinstance(self.accepted, bool):
            raise ValidationError("accepted must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_REVIEW_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_REVIEW_BOUNDARY,
            "ledger_address": self.ledger_address,
            "module_count": self.module_count,
            "attention_count": self.attention_count,
            "evidence_pending_count": self.evidence_pending_count,
            "ready_count": self.ready_count,
            "waiting_count": self.waiting_count,
            "verify_count": self.verify_count,
            "complete_count": self.complete_count,
            "superseded_count": self.superseded_count,
            "next_task_count": self.next_task_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def address_module_workbench_execution_review(
    value: ModuleWorkbenchExecutionReview,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-review")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_REVIEW_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_REVIEW_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_MODULES",
    "MODULE_WORKBENCH_EXECUTION_REVIEW_MAX_NEXT_TASKS",
    "MODULE_WORKBENCH_EXECUTION_REVIEW_VERSION",
    "ModuleWorkbenchExecutionReview",
    "ModuleWorkbenchExecutionReviewItem",
    "ModuleWorkbenchExecutionReviewState",
    "address_module_workbench_execution_review",
    "address_module_workbench_execution_review_item",
]
