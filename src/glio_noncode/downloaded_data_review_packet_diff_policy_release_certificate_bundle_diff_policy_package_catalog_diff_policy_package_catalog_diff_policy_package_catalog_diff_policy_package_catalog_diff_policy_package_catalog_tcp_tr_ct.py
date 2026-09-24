"""Typed contracts for portable review-packet fixed transport catalog diff policy transports."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, hash_bytes

VERSION = "downloaded-data-fixed-transport-catalog-diff-policy-transport-v1"
BOUNDARY = "public_downloaded_data_fixed_transport_catalog_diff_policy_transport"
PACKAGE_PREFIX = "glio-noncode-fixed-transport-catalog-diff-policy-transport"
MANIFEST_PREFIX = PACKAGE_PREFIX + "-manifest"
MEMBER_PREFIX = PACKAGE_PREFIX + "-member"
FILE_NAMES = ("manifest.json", "catalog-diff.json", "policy.json", "policy-audit.json", "review.md")
PAYLOAD_NAMES = FILE_NAMES[1:]
MEDIA_TYPES = {"catalog-diff.json": "application/json", "policy.json": "application/json", "policy-audit.json": "application/json", "review.md": "text/markdown"}
PACKAGE_FORMAT = "zip-stored-utf8-transport-v1"
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.endswith(":pending"):
        return value
    if ":" not in value or len(value.rsplit(":", 1)[-1]) != 64 or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} has the wrong address namespace")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its count bound")
    return value


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember:
    """One deterministic catalog-policy packet member and its addresses."""

    relative_path: str
    media_type: str
    byte_count: int
    byte_address: str
    content_address: str

    def __post_init__(self) -> None:
        if self.relative_path not in PAYLOAD_NAMES:
            raise ValidationError("fixed transport catalog diff policy transport member path is unsupported")
        if MEDIA_TYPES[self.relative_path] != self.media_type:
            raise ValidationError("fixed transport catalog diff policy transport member media type does not replay")
        _count(self.byte_count, "fixed transport catalog diff policy transport member byte count", MAX_MEMBER_BYTES)
        _address(self.byte_address, "fixed transport catalog diff policy transport member byte address", MEMBER_PREFIX + "-bytes")
        _address(self.content_address, "fixed transport catalog diff policy transport member content address", MEMBER_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"relative_path": self.relative_path, "media_type": self.media_type, "byte_count": self.byte_count, "byte_address": self.byte_address, "content_address": self.content_address}


def address_member(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember):
        raise ValidationError("fixed transport catalog diff policy transport member addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


def address_member_bytes(payload: bytes) -> str:
    if not isinstance(payload, bytes) or len(payload) > MAX_MEMBER_BYTES:
        raise ValidationError("fixed transport catalog diff policy transport member payload exceeds its byte bound")
    return hash_bytes(payload, prefix=MEMBER_PREFIX + "-bytes")


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest:
    package_id: str
    version: str
    boundary: str
    diff_address: str
    policy_address: str
    audit_address: str
    policy_state: str
    policy_accepted: bool
    audit_accepted: bool
    members: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember, ...]
    package_format: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.package_id, "fixed transport catalog diff policy transport ID")
        if self.version != VERSION or self.boundary != BOUNDARY or self.package_format != PACKAGE_FORMAT:
            raise ValidationError("fixed transport catalog diff policy transport identity is not current")
        _address(self.diff_address, "fixed transport catalog diff policy transport diff address")
        _address(self.policy_address, "fixed transport catalog diff policy transport policy address")
        _address(self.audit_address, "fixed transport catalog diff policy transport audit address")
        if self.policy_state not in {"ready", "blocked"} or not isinstance(self.policy_accepted, bool) or not isinstance(self.audit_accepted, bool):
            raise ValidationError("fixed transport catalog diff policy transport decision flags are invalid")
        if tuple(item.relative_path for item in self.members) != PAYLOAD_NAMES:
            raise ValidationError("fixed transport catalog diff policy transport payload order is not canonical")
        _address(self.content_address, "fixed transport catalog diff policy transport manifest address", MANIFEST_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "version": self.version, "boundary": self.boundary, "diff_address": self.diff_address, "policy_address": self.policy_address, "audit_address": self.audit_address, "policy_state": self.policy_state, "policy_accepted": self.policy_accepted, "audit_accepted": self.audit_accepted, "members": tuple(item.to_dict() for item in self.members), "package_format": self.package_format, "content_address": self.content_address}


def address_manifest(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest):
        raise ValidationError("fixed transport catalog diff policy transport manifest addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket:
    """A portable ZIP carrying catalog diff, policy, audit, and regenerated review evidence."""

    manifest: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest
    package_bytes: bytes
    package_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.package_bytes, bytes) or len(self.package_bytes) > MAX_PACKAGE_BYTES:
            raise ValidationError("fixed transport catalog diff policy transport bytes exceed their bound")
        _address(self.package_address, "fixed transport catalog diff policy transport address", PACKAGE_PREFIX)
        if self.manifest.content_address.endswith(":pending"):
            raise ValidationError("fixed transport catalog diff policy transport manifest must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.manifest.package_id, "version": VERSION, "boundary": BOUNDARY, "package_format": self.manifest.package_format, "package_byte_count": len(self.package_bytes), "package_address": self.package_address, "manifest": self.manifest.to_dict(), "content_address": self.package_address}

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.manifest.package_id, "version": VERSION, "boundary": BOUNDARY, "package_format": self.manifest.package_format, "package_byte_count": len(self.package_bytes), "package_address": self.package_address, "diff_address": self.manifest.diff_address, "policy_address": self.manifest.policy_address, "audit_address": self.manifest.audit_address, "policy_state": self.manifest.policy_state, "policy_accepted": self.manifest.policy_accepted, "audit_accepted": self.manifest.audit_accepted, "member_count": len(self.manifest.members), "content_address": self.package_address}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet fixed transport catalog diff policy transport manifest", "type": "object", "additionalProperties": False, "required": ["package_id", "version", "boundary", "diff_address", "policy_address", "audit_address", "policy_state", "policy_accepted", "audit_accepted", "members", "package_format", "content_address"], "properties": {"package_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "diff_address": {"type": "string"}, "policy_address": {"type": "string"}, "audit_address": {"type": "string"}, "policy_state": {"enum": ["ready", "blocked"]}, "policy_accepted": {"type": "boolean"}, "audit_accepted": {"type": "boolean"}, "members": {"type": "array", "minItems": len(PAYLOAD_NAMES), "maxItems": len(PAYLOAD_NAMES)}, "package_format": {"const": PACKAGE_FORMAT}, "content_address": {"type": "string"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet fixed transport catalog diff policy transport", "type": "object", "additionalProperties": False, "required": ["package_id", "version", "boundary", "package_format", "package_byte_count", "package_address", "manifest", "content_address"], "properties": {"package_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "package_format": {"const": PACKAGE_FORMAT}, "package_byte_count": {"type": "integer"}, "package_address": {"type": "string"}, "manifest": {"type": "object"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_format": PACKAGE_FORMAT, "members": FILE_NAMES, "payload_members": PAYLOAD_NAMES, "source_free": True, "policy_state_preserved": True, "deterministic": True, "fixed_member_set": True, "regenerated_review": True, "max_package_bytes": MAX_PACKAGE_BYTES, "content_addressed": True}


__all__ = ["BOUNDARY", "FILE_NAMES", "MANIFEST_PREFIX", "MAX_MEMBER_BYTES", "MAX_PACKAGE_BYTES", "MEDIA_TYPES", "PACKAGE_FORMAT", "PACKAGE_PREFIX", "PAYLOAD_NAMES", "VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember", "address_manifest", "address_member", "address_member_bytes", "capabilities", "manifest_schema", "package_schema"]
