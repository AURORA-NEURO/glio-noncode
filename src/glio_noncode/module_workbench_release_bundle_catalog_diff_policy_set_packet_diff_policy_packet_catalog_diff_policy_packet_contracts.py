"""Contracts for portable packet-catalog diff policy review packets."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_VERSION = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_BOUNDARY = "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_FORMAT = "zip-stored-utf8-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MANIFEST = "manifest.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF = "catalog-diff.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE = "policy-gate.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT = "policy-audit.json"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW = "review.md"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_ENTRIES = 5
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_CHECKS = 64
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES = 32 * 1024 * 1024
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_LIMIT = 512


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane(StrEnum):
    ZIP = "zip"
    PATH = "path"
    MANIFEST = "manifest"
    BYTES = "bytes"
    DIFF = "diff"
    POLICY = "policy"
    AUDIT = "audit"
    REVIEW = "review"
    PUBLIC = "public"


def _text(value: Any, field: str, maximum: int = 4096) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")


def _safe_path(value: str) -> bool:
    return isinstance(value, str) and bool(value) and "\\" not in value and ":" not in value and "\x00" not in value and not value.startswith("/") and all(part not in {"", ".", ".."} for part in value.split("/"))


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketMember:
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
            raise ValidationError("catalog-diff policy packet member path is unsafe")
        _text(self.media_type, "media_type", 256)
        _count(self.ordinal, "ordinal", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_ENTRIES - 1)
        _count(self.byte_count, "byte_count", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES)
        _text(self.byte_address, "byte_address", 512)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_member(value: Any) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet-member")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheck:
    check_id: str
    plane: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane):
            raise ValidationError("catalog-diff policy packet check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("catalog-diff policy packet check result must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_check(value: Any) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet-check")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket:
    packet_id: str
    catalog_diff_address: str
    policy_gate_address: str
    policy_audit_address: str
    packet_address: str
    packet_byte_count: int
    members: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketMember, ...]
    packet_bytes: bytes
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "packet_id")
        for field in ("catalog_diff_address", "policy_gate_address", "policy_audit_address", "packet_address", "content_address"):
            _text(getattr(self, field), field, 512)
        _count(self.packet_byte_count, "packet_byte_count", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES)
        if not isinstance(self.members, tuple) or len(self.members) != MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_ENTRIES:
            raise ValidationError("catalog-diff policy packet must contain exactly five members")
        if tuple(item.ordinal for item in self.members) != tuple(range(5)) or len({item.relative_path for item in self.members}) != len(self.members):
            raise ValidationError("catalog-diff policy packet members are not canonical")
        if not isinstance(self.packet_bytes, bytes) or len(self.packet_bytes) != self.packet_byte_count:
            raise ValidationError("catalog-diff policy packet bytes do not conserve packet_byte_count")

    def to_dict(self) -> dict[str, Any]:
        return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_BOUNDARY, "packet_format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_FORMAT, "packet_id": self.packet_id, "catalog_diff_address": self.catalog_diff_address, "policy_gate_address": self.policy_gate_address, "policy_audit_address": self.policy_audit_address, "packet_address": self.packet_address, "packet_byte_count": self.packet_byte_count, "entry_count": len(self.members), "members": [item.to_dict() for item in self.members], "content_address": self.content_address}


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value: Any) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketVerification:
    packet_id: str
    packet_address: str
    catalog_diff_address: str
    policy_gate_address: str
    policy_audit_address: str
    entry_count: int
    present_count: int
    missing_count: int
    checks: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("packet_id", "packet_address", "catalog_diff_address", "policy_gate_address", "policy_audit_address", "content_address"):
            _text(getattr(self, field), field, 512)
        for field in ("entry_count", "present_count", "missing_count"):
            _count(getattr(self, field), field, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_ENTRIES)
        if self.present_count + self.missing_count != self.entry_count or not self.checks or len(self.checks) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_CHECKS:
            raise ValidationError("catalog-diff policy packet verification counts or checks are invalid")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("catalog-diff policy packet checks must be sorted and unique")
        if not isinstance(self.accepted, bool):
            raise ValidationError("catalog-diff policy packet verification acceptance is invalid")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_BOUNDARY, "packet_id": self.packet_id, "packet_address": self.packet_address, "catalog_diff_address": self.catalog_diff_address, "policy_gate_address": self.policy_gate_address, "policy_audit_address": self.policy_audit_address, "entry_count": self.entry_count, "present_count": self.present_count, "missing_count": self.missing_count, "check_count": len(self.checks), "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted, "content_address": self.content_address}


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_verification(value: Any) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet-verification")


__all__ = [name for name in globals() if name.startswith("MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET") or name.startswith("ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket") or name.startswith("address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet")]
