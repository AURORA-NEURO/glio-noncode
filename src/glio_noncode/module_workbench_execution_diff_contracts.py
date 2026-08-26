"""Typed contracts for comparing module execution ledgers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_DIFF_VERSION = "module-workbench-execution-diff-v1"
MODULE_WORKBENCH_EXECUTION_DIFF_BOUNDARY = "public_aggregate_module_workbench_execution_diff"
MODULE_WORKBENCH_EXECUTION_DIFF_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_DIFF_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_DIFF_MAX_CHANGES = 200_000


class ModuleWorkbenchExecutionChangeKind(StrEnum):
    """Task identity comparison result."""

    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _signed_count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")


def _number(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionChange:
    """One stable task-level execution change row."""

    task_id: str
    kind: ModuleWorkbenchExecutionChangeKind
    previous_state: str | None
    current_state: str | None
    completion_delta: float
    evidence_delta: int
    event_delta: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id", 512)
        if not isinstance(self.kind, ModuleWorkbenchExecutionChangeKind):
            raise ValidationError("kind must be a supported execution change kind")
        for field in ("previous_state", "current_state"):
            value = getattr(self, field)
            if value is not None:
                _text(value, field, 128)
        _number(self.completion_delta, "completion_delta")
        _signed_count(self.evidence_delta, "evidence_delta")
        _signed_count(self.event_delta, "event_delta")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_change(
    value: ModuleWorkbenchExecutionChange,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-change")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionDiff:
    """Conserved comparison of two timestamp-free execution ledgers."""

    previous_address: str
    current_address: str
    changes: tuple[ModuleWorkbenchExecutionChange, ...]
    added_count: int
    changed_count: int
    removed_count: int
    unchanged_count: int
    completion_delta: float
    evidence_delta: int
    event_delta: int
    task_delta: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.previous_address, "previous_address")
        _text(self.current_address, "current_address")
        if len(self.changes) > MODULE_WORKBENCH_EXECUTION_DIFF_MAX_CHANGES:
            raise ValidationError("execution diff change limit exceeded")
        ids = tuple(item.task_id for item in self.changes)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("execution diff changes must be sorted and unique")
        for field in ("added_count", "changed_count", "removed_count", "unchanged_count"):
            _count(getattr(self, field), field)
        if sum(
            (self.added_count, self.changed_count, self.removed_count, self.unchanged_count)
        ) != len(self.changes):
            raise ValidationError("execution diff counts do not conserve changes")
        _number(self.completion_delta, "completion_delta")
        for field in ("evidence_delta", "event_delta", "task_delta"):
            _signed_count(getattr(self, field), field)
        if not isinstance(self.accepted, bool):
            raise ValidationError("accepted must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self, *, include_changes: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_DIFF_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_DIFF_BOUNDARY,
            "previous_address": self.previous_address,
            "current_address": self.current_address,
            "change_count": len(self.changes),
            "added_count": self.added_count,
            "changed_count": self.changed_count,
            "removed_count": self.removed_count,
            "unchanged_count": self.unchanged_count,
            "completion_delta": self.completion_delta,
            "evidence_delta": self.evidence_delta,
            "event_delta": self.event_delta,
            "task_delta": self.task_delta,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_changes:
            body["changes"] = [item.to_dict() for item in self.changes]
        return body


def address_module_workbench_execution_diff(
    value: ModuleWorkbenchExecutionDiff,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-diff")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_DIFF_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_DIFF_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_DIFF_MAX_CHANGES",
    "MODULE_WORKBENCH_EXECUTION_DIFF_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_DIFF_VERSION",
    "ModuleWorkbenchExecutionChange",
    "ModuleWorkbenchExecutionChangeKind",
    "ModuleWorkbenchExecutionDiff",
    "address_module_workbench_execution_change",
    "address_module_workbench_execution_diff",
]
