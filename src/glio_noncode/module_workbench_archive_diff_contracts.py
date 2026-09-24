"""Typed contracts for comparing two portable module workbench archives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .module_workbench_diff_contracts import ModuleWorkbenchDiff
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_ARCHIVE_DIFF_VERSION = "module-workbench-archive-diff-v1"
MODULE_WORKBENCH_ARCHIVE_DIFF_BOUNDARY = "public_aggregate_module_workbench_archive_diff"
MODULE_WORKBENCH_ARCHIVE_DIFF_PREFIX = "module-workbench-archive-diff"
MODULE_WORKBENCH_ARCHIVE_DIFF_CHECK_PREFIX = "module-workbench-archive-diff-check"
MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_CHECKS = 16
MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_CHANGES = 20_000
MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_LIMIT = 512
MODULE_WORKBENCH_ARCHIVE_DIFF_DEFAULT_LIMIT = 50


class ModuleWorkbenchArchiveDiffCheckPlane(StrEnum):
    """Independent verification plane for an offline archive comparison."""

    INPUT = "input"
    DIFF = "diff"
    ADDRESS = "address"
    PUBLIC = "public"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveDiffCheck:
    """One independently addressable comparison verification result."""

    check_id: str
    plane: ModuleWorkbenchArchiveDiffCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 128)
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveDiff:
    """A source-free comparison of two addressed workbench report archives."""

    diff_id: str
    previous_archive_address: str
    current_archive_address: str
    previous_workbench_address: str
    current_workbench_address: str
    diff: ModuleWorkbenchDiff
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_id, "diff_id")
        for field in (
            "previous_archive_address",
            "current_archive_address",
            "previous_workbench_address",
            "current_workbench_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if not isinstance(self.diff, ModuleWorkbenchDiff):
            raise ValidationError("archive diff requires a typed workbench diff")
        if self.diff.previous_address != self.previous_workbench_address:
            raise ValidationError("previous workbench address is not conserved")
        if self.diff.current_address != self.current_workbench_address:
            raise ValidationError("current workbench address is not conserved")
        if self.accepted != self.diff.accepted:
            raise ValidationError("archive diff acceptance is not conserved")
        if len(self.diff.changes) > MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_CHANGES:
            raise ValidationError("archive diff change limit exceeded")

    def to_dict(self, *, include_changes: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_ARCHIVE_DIFF_VERSION,
            "boundary": MODULE_WORKBENCH_ARCHIVE_DIFF_BOUNDARY,
            "diff_id": self.diff_id,
            "previous_archive_address": self.previous_archive_address,
            "current_archive_address": self.current_archive_address,
            "previous_workbench_address": self.previous_workbench_address,
            "current_workbench_address": self.current_workbench_address,
            "change_count": len(self.diff.changes),
            "added_count": self.diff.added_count,
            "changed_count": self.diff.changed_count,
            "removed_count": self.diff.removed_count,
            "unchanged_count": self.diff.unchanged_count,
            "score_delta": self.diff.score_delta,
            "task_delta": self.diff.task_delta,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_changes:
            body["diff"] = self.diff.to_dict(include_changes=True)
        return body


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveDiffVerification:
    """Bounded verification result for a portable archive comparison."""

    diff_id: str
    previous_archive_address: str
    current_archive_address: str
    change_count: int
    checks: tuple[ModuleWorkbenchArchiveDiffCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_id, "diff_id")
        _text(self.previous_archive_address, "previous_archive_address")
        _text(self.current_archive_address, "current_archive_address")
        _count(self.change_count, "change_count")
        _text(self.content_address, "content_address")
        if len(self.checks) > MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_CHECKS:
            raise ValidationError("archive diff produced too many checks")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("archive diff checks must be sorted and unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_archive_diff(value: ModuleWorkbenchArchiveDiff) -> str:
    body = value.to_dict(include_changes=True)
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_ARCHIVE_DIFF_PREFIX)


def address_module_workbench_archive_diff_check(
    value: ModuleWorkbenchArchiveDiffCheck,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_ARCHIVE_DIFF_CHECK_PREFIX)


def address_module_workbench_archive_diff_verification(
    value: ModuleWorkbenchArchiveDiffVerification,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-archive-diff-verification")


__all__ = [
    "MODULE_WORKBENCH_ARCHIVE_DIFF_BOUNDARY",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_CHECK_PREFIX",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_CHANGES",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_CHECKS",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_MAX_LIMIT",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_PREFIX",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_VERSION",
    "ModuleWorkbenchArchiveDiff",
    "ModuleWorkbenchArchiveDiffCheck",
    "ModuleWorkbenchArchiveDiffCheckPlane",
    "ModuleWorkbenchArchiveDiffVerification",
    "address_module_workbench_archive_diff",
    "address_module_workbench_archive_diff_check",
    "address_module_workbench_archive_diff_verification",
]
