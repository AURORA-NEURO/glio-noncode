"""Contracts for portable, path-free module workbench report archives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_ARCHIVE_VERSION = "module-workbench-archive-v1"
MODULE_WORKBENCH_ARCHIVE_BOUNDARY = "public_aggregate_module_workbench_archive"
MODULE_WORKBENCH_ARCHIVE_FORMAT = "zip-stored-utf8-v1"
MODULE_WORKBENCH_ARCHIVE_MANIFEST = "manifest.json"
MODULE_WORKBENCH_ARCHIVE_REPORT = "workbench.json"
MODULE_WORKBENCH_ARCHIVE_PREFIX = "module-workbench-archive"
MODULE_WORKBENCH_ARCHIVE_ENTRY_PREFIX = "module-workbench-archive-entry"
MODULE_WORKBENCH_ARCHIVE_CHECK_PREFIX = "module-workbench-archive-check"
MODULE_WORKBENCH_ARCHIVE_VERIFICATION_PREFIX = "module-workbench-archive-verification"
MODULE_WORKBENCH_ARCHIVE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_ARCHIVE_MAX_LIMIT = 512
MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES = 2
MODULE_WORKBENCH_ARCHIVE_MAX_CHECKS = 32
MODULE_WORKBENCH_ARCHIVE_MAX_BYTES = 512 * 1024 * 1024


class ModuleWorkbenchArchiveState(StrEnum):
    """Publication state derived from the archived report."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchArchiveEntryKind(StrEnum):
    """Stable distinction between the archive manifest and report payload."""

    MANIFEST = "manifest"
    REPORT = "report"


class ModuleWorkbenchArchiveCheckPlane(StrEnum):
    """Independent verification planes for an archive."""

    ZIP = "zip"
    PATH = "path"
    MANIFEST = "manifest"
    BYTES = "bytes"
    REPORT = "report"
    PUBLIC = "public"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")


def _safe_path(value: str) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
        or value.startswith("/")
    ):
        return False
    parts = tuple(value.split("/"))
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveEntry:
    """One exact member of a portable workbench archive."""

    entry_id: str
    relative_path: str
    kind: ModuleWorkbenchArchiveEntryKind
    media_type: str
    ordinal: int
    byte_count: int
    line_count: int
    content_address: str

    def __post_init__(self) -> None:
        _text(self.entry_id, "entry_id", 256)
        _text(self.relative_path, "relative_path", 512)
        if not _safe_path(self.relative_path):
            raise ValidationError("archive entry path is unsafe")
        if not isinstance(self.kind, ModuleWorkbenchArchiveEntryKind):
            raise ValidationError("archive entry kind is invalid")
        _text(self.media_type, "media_type", 256)
        _count(self.ordinal, "ordinal")
        _count(self.byte_count, "byte_count", MODULE_WORKBENCH_ARCHIVE_MAX_BYTES)
        _count(self.line_count, "line_count")
        _text(self.content_address, "content_address", 512)
        if self.kind is ModuleWorkbenchArchiveEntryKind.MANIFEST:
            if self.relative_path != MODULE_WORKBENCH_ARCHIVE_MANIFEST or self.ordinal != 0:
                raise ValidationError("archive manifest entry is not canonical")
        if self.kind is ModuleWorkbenchArchiveEntryKind.REPORT:
            if self.relative_path != MODULE_WORKBENCH_ARCHIVE_REPORT or self.ordinal != 1:
                raise ValidationError("archive report entry is not canonical")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_archive_entry(value: ModuleWorkbenchArchiveEntry) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_ARCHIVE_ENTRY_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveCheck:
    """One inspectable archive verification result."""

    check_id: str
    plane: ModuleWorkbenchArchiveCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchArchiveCheckPlane):
            raise ValidationError("archive check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("archive check result must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_archive_check(value: ModuleWorkbenchArchiveCheck) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_ARCHIVE_CHECK_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveVerification:
    """Verification receipt that remains useful when the archive is blocked."""

    archive_id: str
    workbench_address: str
    archive_address: str
    entry_count: int
    present_count: int
    missing_count: int
    checks: tuple[ModuleWorkbenchArchiveCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("archive_id", "workbench_address", "archive_address", "content_address"):
            _text(getattr(self, field), field, 512)
        _count(self.entry_count, "entry_count", MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES)
        _count(self.present_count, "present_count", MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES)
        _count(self.missing_count, "missing_count", MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES)
        _count(len(self.checks), "check_count", MODULE_WORKBENCH_ARCHIVE_MAX_CHECKS)
        if self.present_count + self.missing_count < self.entry_count:
            raise ValidationError("archive verification counts do not conserve")
        if tuple(item.check_id for item in self.checks) != tuple(
            sorted(item.check_id for item in self.checks)
        ):
            raise ValidationError("archive checks must be sorted")
        if not isinstance(self.accepted, bool):
            raise ValidationError("archive verification acceptance must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_archive_verification(
    value: ModuleWorkbenchArchiveVerification,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_ARCHIVE_VERIFICATION_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchive:
    """Deterministic report archive with exact binary and member metadata."""

    archive_id: str
    version: str
    boundary: str
    archive_format: str
    workbench_address: str
    archive_address: str
    archive_byte_count: int
    report_byte_count: int
    entry_count: int
    entries: tuple[ModuleWorkbenchArchiveEntry, ...]
    state: ModuleWorkbenchArchiveState
    accepted: bool
    content_address: str
    archive_bytes: bytes

    def __post_init__(self) -> None:
        for field in (
            "archive_id",
            "version",
            "boundary",
            "archive_format",
            "workbench_address",
            "archive_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        if self.version != MODULE_WORKBENCH_ARCHIVE_VERSION:
            raise ValidationError("archive version is invalid")
        if self.boundary != MODULE_WORKBENCH_ARCHIVE_BOUNDARY:
            raise ValidationError("archive boundary is invalid")
        if self.archive_format != MODULE_WORKBENCH_ARCHIVE_FORMAT:
            raise ValidationError("archive format is invalid")
        _count(self.archive_byte_count, "archive_byte_count", MODULE_WORKBENCH_ARCHIVE_MAX_BYTES)
        _count(self.report_byte_count, "report_byte_count", MODULE_WORKBENCH_ARCHIVE_MAX_BYTES)
        _count(self.entry_count, "entry_count", MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES)
        if not isinstance(self.archive_bytes, bytes):
            raise ValidationError("archive bytes must be bytes")
        if self.archive_byte_count != len(self.archive_bytes):
            raise ValidationError("archive byte count does not match bytes")
        if self.entry_count != MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES:
            raise ValidationError("workbench archive must contain manifest and report entries")
        if len(self.entries) != self.entry_count:
            raise ValidationError("archive entries do not conserve")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.entry_count)):
            raise ValidationError("archive entry ordinals must be contiguous")
        if len({item.entry_id for item in self.entries}) != self.entry_count:
            raise ValidationError("archive entry IDs must be unique")
        if len({item.relative_path for item in self.entries}) != self.entry_count:
            raise ValidationError("archive entry paths must be unique")
        if not isinstance(self.state, ModuleWorkbenchArchiveState):
            raise ValidationError("archive state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("archive acceptance must be boolean")
        if self.accepted != (self.state is ModuleWorkbenchArchiveState.ACCEPTED):
            raise ValidationError("archive state and acceptance do not agree")

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": self.version,
            "boundary": self.boundary,
            "archive_format": self.archive_format,
            "archive_id": self.archive_id,
            "workbench_address": self.workbench_address,
            "archive_address": self.archive_address,
            "archive_byte_count": self.archive_byte_count,
            "report_byte_count": self.report_byte_count,
            "entry_count": self.entry_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def address_module_workbench_archive(value: ModuleWorkbenchArchive) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_ARCHIVE_PREFIX)


__all__ = [
    "MODULE_WORKBENCH_ARCHIVE_BOUNDARY",
    "MODULE_WORKBENCH_ARCHIVE_CHECK_PREFIX",
    "MODULE_WORKBENCH_ARCHIVE_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_ARCHIVE_ENTRY_PREFIX",
    "MODULE_WORKBENCH_ARCHIVE_FORMAT",
    "MODULE_WORKBENCH_ARCHIVE_MANIFEST",
    "MODULE_WORKBENCH_ARCHIVE_MAX_BYTES",
    "MODULE_WORKBENCH_ARCHIVE_MAX_CHECKS",
    "MODULE_WORKBENCH_ARCHIVE_MAX_ENTRIES",
    "MODULE_WORKBENCH_ARCHIVE_MAX_LIMIT",
    "MODULE_WORKBENCH_ARCHIVE_PREFIX",
    "MODULE_WORKBENCH_ARCHIVE_REPORT",
    "MODULE_WORKBENCH_ARCHIVE_VERIFICATION_PREFIX",
    "MODULE_WORKBENCH_ARCHIVE_VERSION",
    "ModuleWorkbenchArchive",
    "ModuleWorkbenchArchiveCheck",
    "ModuleWorkbenchArchiveCheckPlane",
    "ModuleWorkbenchArchiveEntry",
    "ModuleWorkbenchArchiveEntryKind",
    "ModuleWorkbenchArchiveState",
    "ModuleWorkbenchArchiveVerification",
    "address_module_workbench_archive",
    "address_module_workbench_archive_check",
    "address_module_workbench_archive_entry",
    "address_module_workbench_archive_verification",
]
