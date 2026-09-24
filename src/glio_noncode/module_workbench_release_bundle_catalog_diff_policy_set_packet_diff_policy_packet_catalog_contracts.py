"""Contracts for a source-free catalog of portable packet-diff policy packets."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION = (
    "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-v1"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_BOUNDARY = (
    "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_FORMAT = (
    "json-utf8-v1"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX = (
    "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_LIMIT = 512
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES = 256
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_CHECKS = 32
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES = 32 * 1024 * 1024


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane(StrEnum):
    STRUCTURE = "structure"
    ENTRIES = "entries"
    LINEAGE = "lineage"
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
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry:
    """One verified packet descriptor retained without ZIP payload bytes."""

    packet_id: str
    packet_address: str
    packet_content_address: str
    packet_diff_address: str
    policy_gate_address: str
    policy_audit_address: str
    packet_byte_count: int
    member_count: int
    verification_entry_count: int
    verification_check_count: int
    verification_failed_count: int
    policy_gate_accepted: bool
    policy_audit_accepted: bool
    packet_accepted: bool
    ordinal: int
    state: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "packet_id",
            "packet_address",
            "packet_content_address",
            "packet_diff_address",
            "policy_gate_address",
            "policy_audit_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        _count(self.packet_byte_count, "packet_byte_count")
        _count(self.member_count, "member_count")
        _count(self.verification_entry_count, "verification_entry_count")
        _count(self.verification_check_count, "verification_check_count")
        _count(self.verification_failed_count, "verification_failed_count")
        _count(
            self.ordinal,
            "ordinal",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES
            - 1,
        )
        for field in (
            "policy_gate_accepted",
            "policy_audit_accepted",
            "packet_accepted",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValidationError(f"{field} must be boolean")
        if not isinstance(
            self.state,
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState,
        ):
            raise ValidationError("catalog entry state is invalid")
        if self.packet_accepted != (
            self.state
            is ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState.ACCEPTED
        ):
            raise ValidationError("catalog entry state does not conserve packet acceptance")
        if self.verification_failed_count > self.verification_check_count:
            raise ValidationError("verification failure count exceeds check count")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck:
    """One independently replayable catalog verification result."""

    check_id: str
    plane: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(
            self.plane,
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane,
        ):
            raise ValidationError("catalog check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("catalog check result must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification:
    """Verification receipt for a packet catalog, including blocked entries."""

    catalog_id: str
    catalog_address: str
    entry_count: int
    accepted_count: int
    blocked_count: int
    checks: tuple[
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck,
        ...,
    ]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("catalog_id", "catalog_address", "content_address"):
            _text(getattr(self, field), field, 512)
        maximum = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES
        _count(self.entry_count, "entry_count", maximum)
        _count(self.accepted_count, "accepted_count", maximum)
        _count(self.blocked_count, "blocked_count", maximum)
        if self.accepted_count + self.blocked_count != self.entry_count:
            raise ValidationError("catalog verification entry counts do not conserve")
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_CHECKS:
            raise ValidationError("catalog checks are missing or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
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
            "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION,
            "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_BOUNDARY,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "entry_count": self.entry_count,
            "accepted_count": self.accepted_count,
            "blocked_count": self.blocked_count,
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog:
    """Deterministic source-free aggregation of packet review descriptors."""

    catalog_id: str
    version: str
    boundary: str
    catalog_format: str
    catalog_address: str
    catalog_byte_count: int
    total_packet_bytes: int
    entry_count: int
    accepted_count: int
    blocked_count: int
    policy_gate_blocked_count: int
    policy_audit_rejected_count: int
    entries: tuple[
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry,
        ...,
    ]
    state: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState
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
            _text(getattr(self, field), field, 512)
        if self.version != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION:
            raise ValidationError("catalog version is invalid")
        if self.boundary != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_BOUNDARY:
            raise ValidationError("catalog boundary is invalid")
        if self.catalog_format != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_FORMAT:
            raise ValidationError("catalog format is invalid")
        _count(self.catalog_byte_count, "catalog_byte_count", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES)
        _count(self.total_packet_bytes, "total_packet_bytes")
        maximum = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES
        for field in (
            "entry_count",
            "accepted_count",
            "blocked_count",
            "policy_gate_blocked_count",
            "policy_audit_rejected_count",
        ):
            _count(getattr(self, field), field, maximum)
        if not isinstance(self.catalog_bytes, bytes):
            raise ValidationError("catalog bytes must be bytes")
        if len(self.catalog_bytes) != self.catalog_byte_count:
            raise ValidationError("catalog byte count does not match bytes")
        if not self.entries or len(self.entries) != self.entry_count:
            raise ValidationError("catalog entries do not conserve")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.entry_count)):
            raise ValidationError("catalog entry ordinals are not contiguous")
        if len({item.packet_id for item in self.entries}) != self.entry_count:
            raise ValidationError("catalog packet IDs are not unique")
        if len({item.packet_address for item in self.entries}) != self.entry_count:
            raise ValidationError("catalog packet addresses are not unique")
        if not isinstance(self.state, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState):
            raise ValidationError("catalog state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("catalog acceptance is invalid")
        if self.accepted != (
            self.state
            is ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState.ACCEPTED
        ):
            raise ValidationError("catalog state does not conserve acceptance")
        if self.accepted_count + self.blocked_count != self.entry_count:
            raise ValidationError("catalog acceptance counts do not conserve")
        if self.accepted_count != sum(item.packet_accepted for item in self.entries):
            raise ValidationError("catalog accepted count does not conserve entries")
        if self.policy_gate_blocked_count != sum(not item.policy_gate_accepted for item in self.entries):
            raise ValidationError("catalog policy-gate count does not conserve entries")
        if self.policy_audit_rejected_count != sum(not item.policy_audit_accepted for item in self.entries):
            raise ValidationError("catalog policy-audit count does not conserve entries")
        if self.total_packet_bytes != sum(item.packet_byte_count for item in self.entries):
            raise ValidationError("catalog packet bytes do not conserve")

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": self.version,
            "boundary": self.boundary,
            "catalog_format": self.catalog_format,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "catalog_byte_count": self.catalog_byte_count,
            "total_packet_bytes": self.total_packet_bytes,
            "entry_count": self.entry_count,
            "accepted_count": self.accepted_count,
            "blocked_count": self.blocked_count,
            "policy_gate_blocked_count": self.policy_gate_blocked_count,
            "policy_audit_rejected_count": self.policy_audit_rejected_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def _address(value: Any, prefix: str) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=prefix)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry,
) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX + "-entry")


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_check(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck,
) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX + "-check")


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_verification(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification,
) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX + "-verification")


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX)


__all__ = [
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_BOUNDARY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_FORMAT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_CHECKS",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_check",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_verification",
]
