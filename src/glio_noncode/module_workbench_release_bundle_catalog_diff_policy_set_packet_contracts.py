"""Typed contracts for portable policy-set review packets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_VERSION = (
    "module-workbench-release-bundle-catalog-diff-policy-set-packet-v1"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_BOUNDARY = (
    "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_FORMAT = "zip-stored-utf8-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST = "manifest.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE = "policy-set.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT = "policy-set-audit.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW = "review.md"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES = 4
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_CHECKS = 20
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES = 32 * 1024 * 1024
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_LIMIT = 512


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane(StrEnum):
    ZIP = "zip"
    PATH = "path"
    MANIFEST = "manifest"
    BYTES = "bytes"
    GATE = "gate"
    AUDIT = "audit"
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
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember:
    """One exact deterministic ZIP member."""

    member_id: str
    relative_path: str
    media_type: str
    ordinal: int
    byte_count: int
    byte_address: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.member_id, "member_id", 256)
        _text(self.relative_path, "relative_path", 512)
        if not _safe_path(self.relative_path):
            raise ValidationError("policy-set packet member path is unsafe")
        _text(self.media_type, "media_type", 256)
        _count(
            self.ordinal,
            "ordinal",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES - 1,
        )
        _count(
            self.byte_count,
            "byte_count",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES,
        )
        _text(self.byte_address, "byte_address", 512)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_member(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-member"
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck:
    """One independently inspectable packet verification result."""

    check_id: str
    plane: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(
            self.plane, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane
        ):
            raise ValidationError("policy-set packet check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("policy-set packet check result must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_check(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-check"
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket:
    """A portable packet carrying a gate, its audit, and review Markdown."""

    packet_id: str
    policy_set_gate_address: str
    audit_address: str
    packet_address: str
    packet_byte_count: int
    members: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember, ...]
    packet_bytes: bytes
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "packet_id")
        _text(self.policy_set_gate_address, "policy_set_gate_address", 512)
        _text(self.audit_address, "audit_address", 512)
        _text(self.packet_address, "packet_address", 512)
        _count(
            self.packet_byte_count,
            "packet_byte_count",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES,
        )
        if (
            not isinstance(self.members, tuple)
            or len(self.members)
            != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES
        ):
            raise ValidationError("policy-set packet must contain exactly four members")
        if tuple(item.ordinal for item in self.members) != tuple(range(4)):
            raise ValidationError("policy-set packet members must use canonical ordinals")
        if len({item.relative_path for item in self.members}) != len(self.members):
            raise ValidationError("policy-set packet member paths must be unique")
        if (
            not isinstance(self.packet_bytes, bytes)
            or len(self.packet_bytes) != self.packet_byte_count
        ):
            raise ValidationError("policy-set packet bytes do not conserve packet_byte_count")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_VERSION,
            "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_BOUNDARY,
            "packet_id": self.packet_id,
            "policy_set_gate_address": self.policy_set_gate_address,
            "audit_address": self.audit_address,
            "packet_address": self.packet_address,
            "packet_byte_count": self.packet_byte_count,
            "entry_count": len(self.members),
            "members": [item.to_dict() for item in self.members],
            "content_address": self.content_address,
        }


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet"
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification:
    """Verification receipt that remains useful for blocked packets."""

    packet_id: str
    packet_address: str
    policy_set_gate_address: str
    audit_address: str
    entry_count: int
    present_count: int
    missing_count: int
    checks: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "packet_id",
            "packet_address",
            "policy_set_gate_address",
            "audit_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        _count(
            self.entry_count,
            "entry_count",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES,
        )
        _count(
            self.present_count,
            "present_count",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES,
        )
        _count(
            self.missing_count,
            "missing_count",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES,
        )
        if self.present_count + self.missing_count != self.entry_count:
            raise ValidationError("policy-set packet entry counts do not conserve")
        if (
            not self.checks
            or len(self.checks)
            > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_CHECKS
        ):
            raise ValidationError("policy-set packet checks are missing or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("policy-set packet checks must be sorted and unique")
        if not isinstance(self.accepted, bool):
            raise ValidationError("policy-set packet acceptance must be boolean")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_verification(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-verification"
    )


__all__ = [
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_BOUNDARY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_FORMAT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_CHECKS",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_VERSION",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_check",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_member",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_verification",
]
