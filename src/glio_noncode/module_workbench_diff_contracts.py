"""Typed contracts for comparing two module workbench snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_DIFF_VERSION = "module-workbench-diff-v1"
MODULE_WORKBENCH_DIFF_BOUNDARY = "public_aggregate_module_workbench_diff"
MODULE_WORKBENCH_DIFF_MAX_CHANGES = 20_000
MODULE_WORKBENCH_DIFF_MAX_LIMIT = 512
MODULE_WORKBENCH_DIFF_DEFAULT_LIMIT = 50


class ModuleWorkbenchChangeKind(StrEnum):
    """Snapshot comparison result for one module identity."""

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


def _number(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchChange:
    """One stable module-level change row."""

    module_id: str
    kind: ModuleWorkbenchChangeKind
    previous_score: float | None
    current_score: float | None
    previous_depth_band: str | None
    current_depth_band: str | None
    previous_risk: str | None
    current_risk: str | None
    task_delta: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.module_id, "module_id")
        for field in (
            "previous_depth_band",
            "current_depth_band",
            "previous_risk",
            "current_risk",
        ):
            value = getattr(self, field)
            if value is not None:
                _text(value, field, 128)
        for field in ("previous_score", "current_score"):
            value = getattr(self, field)
            if value is not None:
                _number(value, field)
        _count(self.task_delta, "task_delta")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchDiff:
    """Conserved comparison of two timestamp-free workbench reports."""

    previous_address: str
    current_address: str
    changes: tuple[ModuleWorkbenchChange, ...]
    added_count: int
    changed_count: int
    removed_count: int
    unchanged_count: int
    score_delta: float
    task_delta: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.previous_address, "previous_address")
        _text(self.current_address, "current_address")
        _text(self.content_address, "content_address")
        if len(self.changes) > MODULE_WORKBENCH_DIFF_MAX_CHANGES:
            raise ValidationError("workbench diff change limit exceeded")
        ids = tuple(item.module_id for item in self.changes)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("workbench diff changes must be sorted and unique")
        for field in (
            "added_count",
            "changed_count",
            "removed_count",
            "unchanged_count",
        ):
            _count(getattr(self, field), field)
        if sum(
            (
                self.added_count,
                self.changed_count,
                self.removed_count,
                self.unchanged_count,
            )
        ) != len(self.changes):
            raise ValidationError("workbench diff change counts do not conserve rows")
        _number(self.score_delta, "score_delta")
        if not isinstance(self.task_delta, int) or isinstance(self.task_delta, bool):
            raise ValidationError("task_delta must be an integer")

    def to_dict(self, *, include_changes: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_DIFF_VERSION,
            "boundary": MODULE_WORKBENCH_DIFF_BOUNDARY,
            "previous_address": self.previous_address,
            "current_address": self.current_address,
            "change_count": len(self.changes),
            "added_count": self.added_count,
            "changed_count": self.changed_count,
            "removed_count": self.removed_count,
            "unchanged_count": self.unchanged_count,
            "score_delta": self.score_delta,
            "task_delta": self.task_delta,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_changes:
            body["changes"] = [item.to_dict() for item in self.changes]
        return body


def address_module_workbench_change(value: ModuleWorkbenchChange) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-change")


__all__ = [
    "MODULE_WORKBENCH_DIFF_BOUNDARY",
    "MODULE_WORKBENCH_DIFF_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_DIFF_MAX_CHANGES",
    "MODULE_WORKBENCH_DIFF_MAX_LIMIT",
    "MODULE_WORKBENCH_DIFF_VERSION",
    "ModuleWorkbenchChange",
    "ModuleWorkbenchChangeKind",
    "ModuleWorkbenchDiff",
    "address_module_workbench_change",
]
