"""Typed contracts for evidence-gated module workbench execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_VERSION = "module-workbench-execution-v1"
MODULE_WORKBENCH_EXECUTION_BOUNDARY = "public_aggregate_module_workbench_execution"
MODULE_WORKBENCH_EXECUTION_MAX_TASKS = 200_000
MODULE_WORKBENCH_EXECUTION_MAX_EVENTS = 400_000
MODULE_WORKBENCH_EXECUTION_MAX_EVIDENCE = 64
MODULE_WORKBENCH_EXECUTION_MAX_PREREQUISITES = 64
MODULE_WORKBENCH_EXECUTION_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_MAX_LIMIT = 512


class ModuleWorkbenchExecutionState(StrEnum):
    """Lifecycle state for one selected implementation task."""

    PLANNED = "planned"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    SUPERSEDED = "superseded"


class ModuleWorkbenchExecutionAction(StrEnum):
    """Allowed state-changing commands."""

    START = "start"
    COMPLETE = "complete"
    BLOCK = "block"
    UNBLOCK = "unblock"
    SKIP = "skip"
    REOPEN = "reopen"
    SUPERSEDE = "supersede"


class ModuleWorkbenchExecutionEventKind(StrEnum):
    """Persisted event classification for transition history."""

    STARTED = "started"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"
    SKIPPED = "skipped"
    REOPENED = "reopened"
    SUPERSEDED = "superseded"


class ModuleWorkbenchExecutionRequirement(StrEnum):
    """Evidence or review conditions attached to a task."""

    SOURCE = "source"
    TEST = "test"
    DOCUMENTATION = "documentation"
    REVIEW = "review"
    INTEGRATION = "integration"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _optional_text(value: Any, field: str, maximum: int = 4096) -> None:
    if value is not None:
        _text(value, field, maximum)


def _count(value: Any, field: str, *, maximum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")


def _bounded_percent(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if not 0.0 <= float(value) <= 100.0:
        raise ValidationError(f"{field} must be between zero and one hundred")


def _bounded_ratio(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if not 0.0 <= float(value) <= 1.0:
        raise ValidationError(f"{field} must be between zero and one")


def _ordered_unique(values: tuple[str, ...], field: str, maximum: int) -> None:
    if len(values) > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(values)) != values or len(set(values)) != len(values):
        raise ValidationError(f"{field} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionCommand:
    """A caller-supplied transition command without identity metadata."""

    task_id: str
    action: ModuleWorkbenchExecutionAction
    detail: str
    evidence_addresses: tuple[str, ...] = ()
    requirement: ModuleWorkbenchExecutionRequirement | None = None

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id", 512)
        if not isinstance(self.action, ModuleWorkbenchExecutionAction):
            raise ValidationError("action must be a supported execution action")
        _text(self.detail, "detail", 4096)
        _ordered_unique(
            self.evidence_addresses, "evidence_addresses", MODULE_WORKBENCH_EXECUTION_MAX_EVIDENCE
        )
        if self.requirement is not None and not isinstance(
            self.requirement, ModuleWorkbenchExecutionRequirement
        ):
            raise ValidationError("requirement must be a supported execution requirement")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionItem:
    """Current execution state and acceptance conditions for one task."""

    task_id: str
    module_id: str
    family: str
    kind: str
    priority: int
    estimated_impact: float
    prerequisites: tuple[str, ...]
    requirements: tuple[ModuleWorkbenchExecutionRequirement, ...]
    required_evidence_count: int
    initial_state: ModuleWorkbenchExecutionState
    state: ModuleWorkbenchExecutionState
    completion_percent: float
    event_count: int
    evidence_addresses: tuple[str, ...]
    blockers: tuple[str, ...]
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id", 512)
        _text(self.module_id, "module_id", 512)
        _text(self.family, "family", 256)
        _text(self.kind, "kind", 256)
        _count(self.priority, "priority")
        if self.priority > 100:
            raise ValidationError("priority exceeds 100")
        _bounded_ratio(self.estimated_impact, "estimated_impact")
        _ordered_unique(
            self.prerequisites, "prerequisites", MODULE_WORKBENCH_EXECUTION_MAX_PREREQUISITES
        )
        if self.task_id in self.prerequisites:
            raise ValidationError("task cannot depend on itself")
        if not self.requirements:
            raise ValidationError("requirements must not be empty")
        if tuple(sorted(self.requirements, key=lambda item: item.value)) != self.requirements:
            raise ValidationError("requirements must be sorted")
        if len(set(self.requirements)) != len(self.requirements):
            raise ValidationError("requirements must be unique")
        _count(
            self.required_evidence_count,
            "required_evidence_count",
            maximum=MODULE_WORKBENCH_EXECUTION_MAX_EVIDENCE,
        )
        if self.required_evidence_count < 1:
            raise ValidationError("required_evidence_count must be positive")
        if not isinstance(self.initial_state, ModuleWorkbenchExecutionState):
            raise ValidationError("initial_state must be a supported execution state")
        if not isinstance(self.state, ModuleWorkbenchExecutionState):
            raise ValidationError("state must be a supported execution state")
        _bounded_percent(self.completion_percent, "completion_percent")
        _count(self.event_count, "event_count")
        _ordered_unique(
            self.evidence_addresses, "evidence_addresses", MODULE_WORKBENCH_EXECUTION_MAX_EVIDENCE
        )
        _ordered_unique(self.blockers, "blockers", 64)
        if self.state is ModuleWorkbenchExecutionState.COMPLETED:
            if self.completion_percent != 100.0:
                raise ValidationError("completed item must report one hundred percent")
            if len(self.evidence_addresses) < self.required_evidence_count:
                raise ValidationError("completed item lacks required evidence")
        if (
            self.state
            in {
                ModuleWorkbenchExecutionState.BLOCKED,
                ModuleWorkbenchExecutionState.SUPERSEDED,
            }
            and not self.blockers
        ):
            raise ValidationError("blocked or superseded item requires a blocker detail")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_item(value: ModuleWorkbenchExecutionItem) -> str:
    """Return the exact content address for one execution item."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-item")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionEvent:
    """One append-only transition event."""

    event_id: str
    sequence: int
    task_id: str
    from_state: ModuleWorkbenchExecutionState
    to_state: ModuleWorkbenchExecutionState
    kind: ModuleWorkbenchExecutionEventKind
    detail: str
    evidence_addresses: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        _text(self.event_id, "event_id", 512)
        _count(self.sequence, "sequence")
        if self.sequence < 1:
            raise ValidationError("event sequence must start at one")
        _text(self.task_id, "task_id", 512)
        if not isinstance(self.from_state, ModuleWorkbenchExecutionState):
            raise ValidationError("from_state must be a supported execution state")
        if not isinstance(self.to_state, ModuleWorkbenchExecutionState):
            raise ValidationError("to_state must be a supported execution state")
        if not isinstance(self.kind, ModuleWorkbenchExecutionEventKind):
            raise ValidationError("kind must be a supported event kind")
        if self.from_state is self.to_state:
            raise ValidationError("execution event must change state")
        _text(self.detail, "detail", 4096)
        _ordered_unique(
            self.evidence_addresses, "evidence_addresses", MODULE_WORKBENCH_EXECUTION_MAX_EVIDENCE
        )
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_event(value: ModuleWorkbenchExecutionEvent) -> str:
    """Return the exact content address for one transition event."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-event")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionLedger:
    """Immutable task state plus append-only event history."""

    report_address: str
    portfolio_address: str
    items: tuple[ModuleWorkbenchExecutionItem, ...]
    events: tuple[ModuleWorkbenchExecutionEvent, ...]
    total_task_count: int
    planned_count: int
    ready_count: int
    in_progress_count: int
    blocked_count: int
    completed_count: int
    skipped_count: int
    superseded_count: int
    completion_percent: float
    evidence_coverage_percent: float
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.report_address, "report_address")
        _text(self.portfolio_address, "portfolio_address")
        if len(self.items) > MODULE_WORKBENCH_EXECUTION_MAX_TASKS:
            raise ValidationError("execution task limit exceeded")
        if len(self.events) > MODULE_WORKBENCH_EXECUTION_MAX_EVENTS:
            raise ValidationError("execution event limit exceeded")
        task_ids = tuple(item.task_id for item in self.items)
        if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
            raise ValidationError("execution items must be sorted and unique")
        event_sequences = tuple(item.sequence for item in self.events)
        if event_sequences != tuple(range(1, len(self.events) + 1)):
            raise ValidationError("execution events must have contiguous sequences")
        event_ids = tuple(item.event_id for item in self.events)
        if len(event_ids) != len(set(event_ids)):
            raise ValidationError("execution event IDs must be unique")
        for field in (
            "total_task_count",
            "planned_count",
            "ready_count",
            "in_progress_count",
            "blocked_count",
            "completed_count",
            "skipped_count",
            "superseded_count",
        ):
            _count(getattr(self, field), field)
        if self.total_task_count != len(self.items):
            raise ValidationError("total task count does not conserve items")
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
            != self.total_task_count
        ):
            raise ValidationError("execution state counts do not conserve items")
        _bounded_percent(self.completion_percent, "completion_percent")
        _bounded_percent(self.evidence_coverage_percent, "evidence_coverage_percent")
        if not isinstance(self.accepted, bool):
            raise ValidationError("accepted must be boolean")
        _text(self.content_address, "content_address")

    @property
    def terminal_count(self) -> int:
        return self.completed_count + self.skipped_count + self.superseded_count

    @property
    def active_count(self) -> int:
        return self.total_task_count - self.terminal_count

    def to_dict(self, *, include_items: bool = True, include_events: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_BOUNDARY,
            "report_address": self.report_address,
            "portfolio_address": self.portfolio_address,
            "task_count": self.total_task_count,
            "event_count": len(self.events),
            "planned_count": self.planned_count,
            "ready_count": self.ready_count,
            "in_progress_count": self.in_progress_count,
            "blocked_count": self.blocked_count,
            "completed_count": self.completed_count,
            "skipped_count": self.skipped_count,
            "superseded_count": self.superseded_count,
            "terminal_count": self.terminal_count,
            "active_count": self.active_count,
            "completion_percent": self.completion_percent,
            "evidence_coverage_percent": self.evidence_coverage_percent,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        if include_events:
            body["events"] = [item.to_dict() for item in self.events]
        return body


def address_module_workbench_execution_ledger(value: ModuleWorkbenchExecutionLedger) -> str:
    """Return the exact content address for the complete ledger."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-ledger")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_MAX_EVENTS",
    "MODULE_WORKBENCH_EXECUTION_MAX_EVIDENCE",
    "MODULE_WORKBENCH_EXECUTION_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_MAX_PREREQUISITES",
    "MODULE_WORKBENCH_EXECUTION_MAX_TASKS",
    "MODULE_WORKBENCH_EXECUTION_VERSION",
    "ModuleWorkbenchExecutionAction",
    "ModuleWorkbenchExecutionCommand",
    "ModuleWorkbenchExecutionEvent",
    "ModuleWorkbenchExecutionEventKind",
    "ModuleWorkbenchExecutionItem",
    "ModuleWorkbenchExecutionLedger",
    "ModuleWorkbenchExecutionRequirement",
    "ModuleWorkbenchExecutionState",
    "address_module_workbench_execution_event",
    "address_module_workbench_execution_item",
    "address_module_workbench_execution_ledger",
]
