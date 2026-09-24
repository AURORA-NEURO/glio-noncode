"""Contracts for one portable module workbench release-evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION = "module-workbench-release-bundle-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_BOUNDARY = "public_aggregate_module_workbench_release_bundle"
MODULE_WORKBENCH_RELEASE_BUNDLE_FORMAT = "zip-stored-utf8-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST = "manifest.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS = "previous-workbench.zip"
MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT = "current-workbench.zip"
MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF = "archive-diff.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY = "archive-diff-policy.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW = "review.md"
MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX = "module-workbench-release-bundle"
MODULE_WORKBENCH_RELEASE_BUNDLE_ENTRY_PREFIX = "module-workbench-release-bundle-entry"
MODULE_WORKBENCH_RELEASE_BUNDLE_CHECK_PREFIX = "module-workbench-release-bundle-check"
MODULE_WORKBENCH_RELEASE_BUNDLE_VERIFICATION_PREFIX = "module-workbench-release-bundle-verification"
MODULE_WORKBENCH_RELEASE_BUNDLE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_LIMIT = 512
MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES = 6
MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_CHECKS = 24
MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES = 256 * 1024 * 1024


class ModuleWorkbenchReleaseBundleState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchReleaseBundleEntryKind(StrEnum):
    MANIFEST = "manifest"
    WORKBENCH_ARCHIVE = "workbench_archive"
    DIFF = "diff"
    POLICY = "policy"
    REVIEW = "review"


class ModuleWorkbenchReleaseBundleCheckPlane(StrEnum):
    ZIP = "zip"
    PATH = "path"
    BYTES = "bytes"
    MANIFEST = "manifest"
    ARCHIVE = "archive"
    DIFF = "diff"
    POLICY = "policy"
    PUBLIC = "public"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
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
    return all(part not in {"", ".", ".."} for part in value.split("/"))


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleEntry:
    """One exact member of the release-evidence ZIP."""

    entry_id: str
    relative_path: str
    kind: ModuleWorkbenchReleaseBundleEntryKind
    media_type: str
    ordinal: int
    byte_count: int
    line_count: int
    content_address: str

    def __post_init__(self) -> None:
        _text(self.entry_id, "entry_id", 256)
        _text(self.relative_path, "relative_path", 512)
        if not _safe_path(self.relative_path):
            raise ValidationError("release bundle entry path is unsafe")
        if not isinstance(self.kind, ModuleWorkbenchReleaseBundleEntryKind):
            raise ValidationError("release bundle entry kind is invalid")
        _text(self.media_type, "media_type", 256)
        _count(self.ordinal, "ordinal", MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES - 1)
        _count(self.byte_count, "byte_count")
        _count(self.line_count, "line_count")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCheck:
    """One independently inspectable bundle verification result."""

    check_id: str
    plane: ModuleWorkbenchReleaseBundleCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchReleaseBundleCheckPlane):
            raise ValidationError("release bundle check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("release bundle check result must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleVerification:
    """Bounded verification receipt that remains useful for blocked bundles."""

    bundle_id: str
    bundle_address: str
    entry_count: int
    present_count: int
    missing_count: int
    checks: tuple[ModuleWorkbenchReleaseBundleCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("bundle_id", "bundle_address", "content_address"):
            _text(getattr(self, field), field)
        _count(self.entry_count, "entry_count", MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES)
        _count(self.present_count, "present_count", MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES)
        _count(self.missing_count, "missing_count", MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES)
        if self.present_count + self.missing_count != self.entry_count:
            raise ValidationError("release bundle entry counts do not conserve")
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_CHECKS:
            raise ValidationError("release bundle checks are missing or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("release bundle checks must be sorted and unique")
        if not isinstance(self.accepted, bool):
            raise ValidationError("release bundle verification acceptance must be boolean")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_address": self.bundle_address,
            "entry_count": self.entry_count,
            "present_count": self.present_count,
            "missing_count": self.missing_count,
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundle:
    """Deterministic multi-artifact evidence handoff."""

    bundle_id: str
    version: str
    boundary: str
    bundle_format: str
    previous_archive_address: str
    current_archive_address: str
    diff_address: str
    policy_gate_address: str
    bundle_address: str
    bundle_byte_count: int
    entry_count: int
    entries: tuple[ModuleWorkbenchReleaseBundleEntry, ...]
    state: ModuleWorkbenchReleaseBundleState
    accepted: bool
    content_address: str
    bundle_bytes: bytes

    def __post_init__(self) -> None:
        for field in (
            "bundle_id",
            "version",
            "boundary",
            "bundle_format",
            "previous_archive_address",
            "current_archive_address",
            "diff_address",
            "policy_gate_address",
            "bundle_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if self.version != MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION:
            raise ValidationError("release bundle version is invalid")
        if self.boundary != MODULE_WORKBENCH_RELEASE_BUNDLE_BOUNDARY:
            raise ValidationError("release bundle boundary is invalid")
        if self.bundle_format != MODULE_WORKBENCH_RELEASE_BUNDLE_FORMAT:
            raise ValidationError("release bundle format is invalid")
        _count(
            self.bundle_byte_count, "bundle_byte_count", MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES
        )
        _count(self.entry_count, "entry_count", MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES)
        if (
            not isinstance(self.bundle_bytes, bytes)
            or len(self.bundle_bytes) != self.bundle_byte_count
        ):
            raise ValidationError("release bundle bytes do not match declared size")
        if len(self.entries) != self.entry_count or not self.entries:
            raise ValidationError("release bundle entries do not conserve")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.entry_count)):
            raise ValidationError("release bundle entry ordinals are not contiguous")
        paths = tuple(item.relative_path for item in self.entries)
        if len(paths) != len(set(paths)):
            raise ValidationError("release bundle entry paths are not unique")
        if self.accepted != (self.state is ModuleWorkbenchReleaseBundleState.ACCEPTED):
            raise ValidationError("release bundle state does not conserve acceptance")

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "bundle_id": self.bundle_id,
            "version": self.version,
            "boundary": self.boundary,
            "bundle_format": self.bundle_format,
            "previous_archive_address": self.previous_archive_address,
            "current_archive_address": self.current_archive_address,
            "diff_address": self.diff_address,
            "policy_gate_address": self.policy_gate_address,
            "bundle_address": self.bundle_address,
            "bundle_byte_count": self.bundle_byte_count,
            "entry_count": self.entry_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def address_module_workbench_release_bundle_entry(
    value: ModuleWorkbenchReleaseBundleEntry,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_ENTRY_PREFIX)


def address_module_workbench_release_bundle_check(
    value: ModuleWorkbenchReleaseBundleCheck,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CHECK_PREFIX)


def address_module_workbench_release_bundle_verification(
    value: ModuleWorkbenchReleaseBundleVerification,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_VERIFICATION_PREFIX)


def address_module_workbench_release_bundle(
    value: ModuleWorkbenchReleaseBundle,
) -> str:
    body = value.to_dict(include_entries=True)
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX)


__all__ = [
    "MODULE_WORKBENCH_RELEASE_BUNDLE_BOUNDARY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CURRENT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_ENTRY_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_FORMAT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_MANIFEST",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_BYTES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_CHECKS",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_ENTRIES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_MAX_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_POLICY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_PREVIOUS",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_REVIEW",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_VERSION",
    "ModuleWorkbenchReleaseBundle",
    "ModuleWorkbenchReleaseBundleCheck",
    "ModuleWorkbenchReleaseBundleCheckPlane",
    "ModuleWorkbenchReleaseBundleEntry",
    "ModuleWorkbenchReleaseBundleEntryKind",
    "ModuleWorkbenchReleaseBundleState",
    "ModuleWorkbenchReleaseBundleVerification",
    "address_module_workbench_release_bundle",
    "address_module_workbench_release_bundle_check",
    "address_module_workbench_release_bundle_entry",
    "address_module_workbench_release_bundle_verification",
]
