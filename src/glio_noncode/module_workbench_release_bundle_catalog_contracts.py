"""Contracts for an addressed catalog of portable workbench bundles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERSION = "module-workbench-release-bundle-catalog-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_BOUNDARY = (
    "public_aggregate_module_workbench_release_bundle_catalog"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_FORMAT = "json-utf8-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_PREFIX = "module-workbench-release-bundle-catalog"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_ENTRY_PREFIX = (
    "module-workbench-release-bundle-catalog-entry"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_CHECK_PREFIX = (
    "module-workbench-release-bundle-catalog-check"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERIFICATION_PREFIX = (
    "module-workbench-release-bundle-catalog-verification"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_QUERY_PREFIX = (
    "module-workbench-release-bundle-catalog-query"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_LIMIT = 512
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES = 128
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_CHECKS = 16
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_BYTES = 16 * 1024 * 1024


class ModuleWorkbenchReleaseBundleCatalogState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchReleaseBundleCatalogCheckPlane(StrEnum):
    STRUCTURE = "structure"
    REFERENCES = "references"
    STATE = "state"
    BYTES = "bytes"
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


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogEntry:
    """One verified bundle reference retained by the source-free catalog."""

    bundle_id: str
    bundle_address: str
    bundle_content_address: str
    verification_address: str
    previous_archive_address: str
    current_archive_address: str
    diff_address: str
    policy_gate_address: str
    bundle_byte_count: int
    bundle_entry_count: int
    verification_failed_count: int
    ordinal: int
    state: ModuleWorkbenchReleaseBundleCatalogState
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "bundle_id",
            "bundle_address",
            "bundle_content_address",
            "verification_address",
            "previous_archive_address",
            "current_archive_address",
            "diff_address",
            "policy_gate_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        _count(self.bundle_byte_count, "bundle_byte_count")
        _count(self.bundle_entry_count, "bundle_entry_count")
        _count(self.verification_failed_count, "verification_failed_count")
        _count(self.ordinal, "ordinal", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES - 1)
        if not isinstance(self.state, ModuleWorkbenchReleaseBundleCatalogState):
            raise ValidationError("catalog entry state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("catalog entry acceptance is invalid")
        if self.accepted != (self.state is ModuleWorkbenchReleaseBundleCatalogState.ACCEPTED):
            raise ValidationError("catalog entry state does not conserve acceptance")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogCheck:
    """One independently inspectable catalog verification result."""

    check_id: str
    plane: ModuleWorkbenchReleaseBundleCatalogCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchReleaseBundleCatalogCheckPlane):
            raise ValidationError("catalog check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("catalog check result must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogVerification:
    """Structural receipt for a catalog, including blocked evidence."""

    catalog_id: str
    catalog_address: str
    entry_count: int
    checks: tuple[ModuleWorkbenchReleaseBundleCatalogCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("catalog_id", "catalog_address", "content_address"):
            _text(getattr(self, field), field)
        _count(self.entry_count, "entry_count", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES)
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_CHECKS:
            raise ValidationError("catalog checks are missing or excessive")
        check_ids = tuple(item.check_id for item in self.checks)
        if check_ids != tuple(sorted(check_ids)) or len(check_ids) != len(set(check_ids)):
            raise ValidationError("catalog checks must be sorted and unique")
        if not isinstance(self.accepted, bool):
            raise ValidationError("catalog verification acceptance is invalid")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "entry_count": self.entry_count,
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalog:
    """Deterministic source-free aggregation of verified bundle references."""

    catalog_id: str
    version: str
    boundary: str
    catalog_format: str
    catalog_address: str
    catalog_byte_count: int
    total_bundle_bytes: int
    entry_count: int
    entries: tuple[ModuleWorkbenchReleaseBundleCatalogEntry, ...]
    state: ModuleWorkbenchReleaseBundleCatalogState
    accepted: bool
    content_address: str
    catalog_bytes: bytes

    def __post_init__(self) -> None:
        for field in (
            "catalog_id",
            "version",
            "boundary",
            "catalog_format",
            "catalog_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        if self.version != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERSION:
            raise ValidationError("catalog version is invalid")
        if self.boundary != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_BOUNDARY:
            raise ValidationError("catalog boundary is invalid")
        if self.catalog_format != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_FORMAT:
            raise ValidationError("catalog format is invalid")
        _count(
            self.catalog_byte_count,
            "catalog_byte_count",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_BYTES,
        )
        _count(self.total_bundle_bytes, "total_bundle_bytes")
        _count(self.entry_count, "entry_count", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES)
        if not isinstance(self.catalog_bytes, bytes):
            raise ValidationError("catalog bytes must be bytes")
        if len(self.catalog_bytes) != self.catalog_byte_count:
            raise ValidationError("catalog byte count does not match bytes")
        if not self.entries or len(self.entries) != self.entry_count:
            raise ValidationError("catalog entries do not conserve")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.entry_count)):
            raise ValidationError("catalog entry ordinals are not contiguous")
        if len({item.bundle_id for item in self.entries}) != self.entry_count:
            raise ValidationError("catalog bundle IDs are not unique")
        if len({item.bundle_address for item in self.entries}) != self.entry_count:
            raise ValidationError("catalog bundle addresses are not unique")
        if not isinstance(self.state, ModuleWorkbenchReleaseBundleCatalogState):
            raise ValidationError("catalog state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("catalog acceptance is invalid")
        if self.accepted != (self.state is ModuleWorkbenchReleaseBundleCatalogState.ACCEPTED):
            raise ValidationError("catalog state does not conserve acceptance")
        if self.total_bundle_bytes != sum(item.bundle_byte_count for item in self.entries):
            raise ValidationError("catalog bundle bytes do not conserve")

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "catalog_id": self.catalog_id,
            "version": self.version,
            "boundary": self.boundary,
            "catalog_format": self.catalog_format,
            "catalog_address": self.catalog_address,
            "catalog_byte_count": self.catalog_byte_count,
            "total_bundle_bytes": self.total_bundle_bytes,
            "entry_count": self.entry_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def address_module_workbench_release_bundle_catalog_entry(
    value: ModuleWorkbenchReleaseBundleCatalogEntry,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_ENTRY_PREFIX)


def address_module_workbench_release_bundle_catalog_check(
    value: ModuleWorkbenchReleaseBundleCatalogCheck,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_CHECK_PREFIX)


def address_module_workbench_release_bundle_catalog_verification(
    value: ModuleWorkbenchReleaseBundleCatalogVerification,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body,
        prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERIFICATION_PREFIX,
    )


def address_module_workbench_release_bundle_catalog(
    value: ModuleWorkbenchReleaseBundleCatalog,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_PREFIX)


__all__ = [
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_BOUNDARY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_CHECK_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_ENTRY_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_FORMAT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_BYTES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_CHECKS",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_ENTRIES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_MAX_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_QUERY_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERIFICATION_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_VERSION",
    "ModuleWorkbenchReleaseBundleCatalog",
    "ModuleWorkbenchReleaseBundleCatalogCheck",
    "ModuleWorkbenchReleaseBundleCatalogCheckPlane",
    "ModuleWorkbenchReleaseBundleCatalogEntry",
    "ModuleWorkbenchReleaseBundleCatalogState",
    "ModuleWorkbenchReleaseBundleCatalogVerification",
    "address_module_workbench_release_bundle_catalog",
    "address_module_workbench_release_bundle_catalog_check",
    "address_module_workbench_release_bundle_catalog_entry",
    "address_module_workbench_release_bundle_catalog_verification",
]
