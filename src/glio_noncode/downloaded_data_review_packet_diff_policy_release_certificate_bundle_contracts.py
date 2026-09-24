"""Typed contracts for deterministic downloaded-data release bundles."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, hash_bytes

VERSION = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff_policy_release_certificate_bundle"
BUNDLE_PREFIX = "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle"
MANIFEST_PREFIX = BUNDLE_PREFIX + "-manifest"
MEMBER_PREFIX = BUNDLE_PREFIX + "-member"
CERTIFICATE_PREFIX = "glio-noncode-download-review-packet-diff-policy-release-certificate"
CERTIFICATE_AUDIT_PREFIX = CERTIFICATE_PREFIX + "-audit"
RUN_PREFIX = "glio-noncode-download-review-packet-diff-policy-run"
RUN_AUDIT_PREFIX = RUN_PREFIX + "-audit"
PACKAGE_PREFIX = "glio-noncode-download-review-packet-diff-policy-package"
FILE_NAMES = ("manifest.json", "certificate.json", "certificate-audit.json", "run.json", "run-audit.json", "package.zip", "review.md")
PAYLOAD_NAMES = FILE_NAMES[1:]
MEDIA_TYPES = {
    "certificate.json": "application/json",
    "certificate-audit.json": "application/json",
    "run.json": "application/json",
    "run-audit.json": "application/json",
    "package.zip": "application/zip",
    "review.md": "text/markdown",
}
BUNDLE_FORMAT = "zip-stored-utf8-v1"
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 4096)
    if value.endswith(":pending"):
        return value
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64 or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its count bound")
    return value


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember:
    """One deterministic bundle member and its byte/content addresses."""

    relative_path: str
    media_type: str
    byte_count: int
    byte_address: str
    content_address: str

    def __post_init__(self) -> None:
        if self.relative_path not in PAYLOAD_NAMES:
            raise ValidationError("release bundle member path is not in the fixed payload set")
        if MEDIA_TYPES[self.relative_path] != self.media_type:
            raise ValidationError("release bundle member media type does not replay")
        _count(self.byte_count, "release bundle member byte count", MAX_MEMBER_BYTES)
        _address(self.byte_address, "release bundle member byte address", MEMBER_PREFIX + "-bytes")
        _address(self.content_address, "release bundle member content address", MEMBER_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"relative_path": self.relative_path, "media_type": self.media_type, "byte_count": self.byte_count, "byte_address": self.byte_address, "content_address": self.content_address}


def address_member(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember):
        raise ValidationError("release bundle member addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


def address_member_bytes(payload: bytes) -> str:
    if not isinstance(payload, bytes) or len(payload) > MAX_MEMBER_BYTES:
        raise ValidationError("release bundle member payload is outside its byte bound")
    return hash_bytes(payload, prefix=MEMBER_PREFIX + "-bytes")


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest:
    bundle_id: str
    version: str
    boundary: str
    certificate_address: str
    certificate_audit_address: str
    run_address: str
    run_audit_address: str
    package_address: str
    package_byte_count: int
    release_state: str
    release_eligible: bool
    members: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember, ...]
    bundle_format: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.bundle_id, "release bundle ID")
        if self.version != VERSION or self.boundary != BOUNDARY or self.bundle_format != BUNDLE_FORMAT:
            raise ValidationError("release bundle identity is not current")
        _address(self.certificate_address, "release bundle certificate address", CERTIFICATE_PREFIX)
        _address(self.certificate_audit_address, "release bundle certificate audit address", CERTIFICATE_AUDIT_PREFIX)
        _address(self.run_address, "release bundle run address", RUN_PREFIX)
        _address(self.run_audit_address, "release bundle run audit address", RUN_AUDIT_PREFIX)
        _address(self.package_address, "release bundle package address", PACKAGE_PREFIX)
        _count(self.package_byte_count, "release bundle package byte count", MAX_MEMBER_BYTES)
        if self.release_state not in {"ready", "blocked"} or not isinstance(self.release_eligible, bool) or self.release_eligible != (self.release_state == "ready"):
            raise ValidationError("release bundle decision does not replay")
        if tuple(item.relative_path for item in self.members) != PAYLOAD_NAMES:
            raise ValidationError("release bundle payload order is not canonical")
        _address(self.content_address, "release bundle manifest address", MANIFEST_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "version": self.version,
            "boundary": self.boundary,
            "certificate_address": self.certificate_address,
            "certificate_audit_address": self.certificate_audit_address,
            "run_address": self.run_address,
            "run_audit_address": self.run_audit_address,
            "package_address": self.package_address,
            "package_byte_count": self.package_byte_count,
            "release_state": self.release_state,
            "release_eligible": self.release_eligible,
            "members": tuple(item.to_dict() for item in self.members),
            "bundle_format": self.bundle_format,
            "content_address": self.content_address,
        }


def address_manifest(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest):
        raise ValidationError("release bundle manifest addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle:
    """A portable ZIP carrying the complete source-free release decision."""

    manifest: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest
    bundle_bytes: bytes
    bundle_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_bytes, bytes) or len(self.bundle_bytes) > MAX_BUNDLE_BYTES:
            raise ValidationError("release bundle bytes are outside their bound")
        _address(self.bundle_address, "release bundle address", BUNDLE_PREFIX)
        if self.manifest.content_address.endswith(":pending"):
            raise ValidationError("release bundle manifest must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.manifest.bundle_id,
            "version": VERSION,
            "boundary": BOUNDARY,
            "bundle_format": self.manifest.bundle_format,
            "bundle_byte_count": len(self.bundle_bytes),
            "bundle_address": self.bundle_address,
            "manifest": self.manifest.to_dict(),
            "content_address": self.bundle_address,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "bundle_id": self.manifest.bundle_id,
            "version": VERSION,
            "boundary": BOUNDARY,
            "bundle_format": self.manifest.bundle_format,
            "bundle_byte_count": len(self.bundle_bytes),
            "bundle_address": self.bundle_address,
            "certificate_address": self.manifest.certificate_address,
            "certificate_audit_address": self.manifest.certificate_audit_address,
            "run_address": self.manifest.run_address,
            "run_audit_address": self.manifest.run_audit_address,
            "package_address": self.manifest.package_address,
            "package_byte_count": self.manifest.package_byte_count,
            "release_state": self.manifest.release_state,
            "release_eligible": self.manifest.release_eligible,
            "member_count": len(self.manifest.members),
            "content_address": self.bundle_address,
        }


def manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data release certificate bundle manifest",
        "type": "object",
        "additionalProperties": False,
        "required": ["bundle_id", "version", "boundary", "certificate_address", "certificate_audit_address", "run_address", "run_audit_address", "package_address", "package_byte_count", "release_state", "release_eligible", "members", "bundle_format", "content_address"],
        "properties": {
            "bundle_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY},
            "certificate_address": {"type": "string"}, "certificate_audit_address": {"type": "string"}, "run_address": {"type": "string"}, "run_audit_address": {"type": "string"}, "package_address": {"type": "string"}, "package_byte_count": {"type": "integer"},
            "release_state": {"enum": ["ready", "blocked"]}, "release_eligible": {"type": "boolean"}, "members": {"type": "array", "minItems": len(PAYLOAD_NAMES), "maxItems": len(PAYLOAD_NAMES)}, "bundle_format": {"const": BUNDLE_FORMAT}, "content_address": {"type": "string"},
        },
    }


def bundle_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data release certificate bundle",
        "type": "object",
        "additionalProperties": False,
        "required": ["bundle_id", "version", "boundary", "bundle_format", "bundle_byte_count", "bundle_address", "manifest", "content_address"],
        "properties": {"bundle_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "bundle_format": {"const": BUNDLE_FORMAT}, "bundle_byte_count": {"type": "integer"}, "bundle_address": {"type": "string"}, "manifest": {"type": "object"}, "content_address": {"type": "string"}},
    }


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "bundle_format": BUNDLE_FORMAT, "members": FILE_NAMES, "payload_members": PAYLOAD_NAMES, "source_free": True, "nested_package_preserved": True, "decision_preserved": True, "deterministic": True, "max_bundle_bytes": MAX_BUNDLE_BYTES, "content_addressed": True}


__all__ = [
    "BOUNDARY", "BUNDLE_FORMAT", "BUNDLE_PREFIX", "FILE_NAMES", "MANIFEST_PREFIX", "MAX_BUNDLE_BYTES", "MAX_MEMBER_BYTES", "MEDIA_TYPES", "PAYLOAD_NAMES", "VERSION",
    "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember", "address_manifest", "address_member", "address_member_bytes", "bundle_schema", "capabilities", "manifest_schema",
]
