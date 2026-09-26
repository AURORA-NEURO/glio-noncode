"""Typed contracts for module667 policy-decision transports."""
# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .downloaded_data_review_packet_fixed_transport_catalog_diff_policy_666_ct import BOUNDARY as POLICY_BOUNDARY, POLICY_PREFIX
from .errors import ValidationError
from .serialization import content_hash, hash_bytes

VERSION = POLICY_PREFIX + "-transport-v1"
BOUNDARY = "public_" + VERSION.replace("-", "_")
PACKAGE_PREFIX = POLICY_PREFIX + "-transport"
MANIFEST_PREFIX = PACKAGE_PREFIX + "-manifest"
MEMBER_PREFIX = PACKAGE_PREFIX + "-member"
FILE_NAMES = ("manifest.json", "catalog-diff.json", "policy.json", "policy-audit.json", "review.md")
PAYLOAD_NAMES = FILE_NAMES[1:]
MEDIA_TYPES = {"catalog-diff.json": "application/json", "policy.json": "application/json", "policy-audit.json": "application/json", "review.md": "text/markdown"}
PACKAGE_FORMAT = "zip-stored-utf8-transport-v1"
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096)
    if allow_pending and value.endswith(":pending"):
        return value
    digest = value.rsplit(":", 1)[-1]
    if ":" not in value or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a canonical content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


@dataclass(frozen=True)
class Member:
    relative_path: str
    media_type: str
    byte_count: int
    byte_address: str
    content_address: str

    def __post_init__(self) -> None:
        if self.relative_path not in PAYLOAD_NAMES or MEDIA_TYPES[self.relative_path] != self.media_type:
            raise ValidationError("module667 member path or media type is unsupported")
        _count(self.byte_count, "module667 member byte count", MAX_MEMBER_BYTES)
        _address(self.byte_address, "module667 member byte address", MEMBER_PREFIX + "-bytes")
        _address(self.content_address, "module667 member content address", MEMBER_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_member(self) != self.content_address:
            raise ValidationError("module667 member address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"relative_path": self.relative_path, "media_type": self.media_type, "byte_count": self.byte_count, "byte_address": self.byte_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Member":
        if set(value) != {"relative_path", "media_type", "byte_count", "byte_address", "content_address"}:
            raise ValidationError("module667 member fields are not exact")
        return cls(value["relative_path"], value["media_type"], value["byte_count"], value["byte_address"], value["content_address"])


def address_member(value: Member) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


def address_member_bytes(payload: bytes) -> str:
    if not isinstance(payload, bytes) or len(payload) > MAX_MEMBER_BYTES:
        raise ValidationError("module667 member payload exceeds its byte bound")
    return hash_bytes(payload, prefix=MEMBER_PREFIX + "-bytes")


@dataclass(frozen=True)
class Manifest:
    package_id: str
    version: str
    boundary: str
    diff_address: str
    policy_address: str
    audit_address: str
    policy_state: str
    policy_accepted: bool
    audit_accepted: bool
    members: tuple[Member, ...]
    package_format: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.package_id, "module667 package ID")
        if self.version != VERSION or self.boundary != BOUNDARY or self.package_format != PACKAGE_FORMAT:
            raise ValidationError("module667 manifest identity is not current")
        _address(self.diff_address, "module667 diff address")
        _address(self.policy_address, "module667 policy address")
        _address(self.audit_address, "module667 audit address")
        if self.policy_state not in {"ready", "blocked"} or not isinstance(self.policy_accepted, bool) or not isinstance(self.audit_accepted, bool):
            raise ValidationError("module667 decision flags are invalid")
        if tuple(item.relative_path for item in self.members) != PAYLOAD_NAMES:
            raise ValidationError("module667 payload order is not canonical")
        _address(self.content_address, "module667 manifest address", MANIFEST_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("module667 manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "version": VERSION, "boundary": BOUNDARY, "diff_address": self.diff_address, "policy_address": self.policy_address, "audit_address": self.audit_address, "policy_state": self.policy_state, "policy_accepted": self.policy_accepted, "audit_accepted": self.audit_accepted, "members": tuple(item.to_dict() for item in self.members), "package_format": PACKAGE_FORMAT, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Manifest":
        fields = {"package_id", "version", "boundary", "diff_address", "policy_address", "audit_address", "policy_state", "policy_accepted", "audit_accepted", "members", "package_format", "content_address"}
        if set(value) != fields:
            raise ValidationError("module667 manifest fields are not exact")
        return cls(value["package_id"], value["version"], value["boundary"], value["diff_address"], value["policy_address"], value["audit_address"], value["policy_state"], value["policy_accepted"], value["audit_accepted"], tuple(Member.from_mapping(item) for item in value["members"]), value["package_format"], value["content_address"])


def address_manifest(value: Manifest) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


@dataclass(frozen=True)
class Transport:
    manifest: Manifest
    package_bytes: bytes
    package_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.package_bytes, bytes) or len(self.package_bytes) > MAX_PACKAGE_BYTES:
            raise ValidationError("module667 package bytes exceed their bound")
        _address(self.package_address, "module667 package address", PACKAGE_PREFIX)
        if self.manifest.content_address.endswith(":pending"):
            raise ValidationError("module667 manifest must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.manifest.package_id, "version": VERSION, "boundary": BOUNDARY, "package_format": PACKAGE_FORMAT, "package_byte_count": len(self.package_bytes), "package_address": self.package_address, "manifest": self.manifest.to_dict(), "content_address": self.package_address}

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.manifest.package_id, "version": VERSION, "boundary": BOUNDARY, "package_format": PACKAGE_FORMAT, "package_byte_count": len(self.package_bytes), "package_address": self.package_address, "manifest_address": self.manifest.content_address, "diff_address": self.manifest.diff_address, "policy_address": self.manifest.policy_address, "audit_address": self.manifest.audit_address, "policy_state": self.manifest.policy_state, "policy_accepted": self.manifest.policy_accepted, "audit_accepted": self.manifest.audit_accepted, "member_count": len(self.manifest.members), "content_address": self.package_address}


def package_schema() -> dict[str, Any]:
    fields = ("package_id", "version", "boundary", "package_format", "package_byte_count", "package_address", "manifest", "content_address")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module667 fixed transport", "type": "object", "additionalProperties": False, "required": list(fields), "properties": {"package_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "package_format": {"const": PACKAGE_FORMAT}, "package_byte_count": {"type": "integer"}, "manifest": {"type": "object"}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    fields = ("package_id", "version", "boundary", "diff_address", "policy_address", "audit_address", "policy_state", "policy_accepted", "audit_accepted", "members", "package_format", "content_address")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module667 manifest", "type": "object", "additionalProperties": False, "required": list(fields), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "members": {"type": "array", "minItems": len(PAYLOAD_NAMES), "maxItems": len(PAYLOAD_NAMES)}, "package_format": {"const": PACKAGE_FORMAT}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_format": PACKAGE_FORMAT, "members": FILE_NAMES, "payload_members": PAYLOAD_NAMES, "source_free": True, "content_addressed": True, "deterministic": True, "fixed_member_set": True, "policy_evidence_preserved": True, "regenerated_review": True, "policy_boundary": POLICY_BOUNDARY, "max_package_bytes": MAX_PACKAGE_BYTES, "max_member_bytes": MAX_MEMBER_BYTES}


Package = Transport
__all__ = ["BOUNDARY", "FILE_NAMES", "FIXED_ZIP_DATE", "MANIFEST_PREFIX", "MAX_MEMBER_BYTES", "MAX_PACKAGE_BYTES", "MEDIA_TYPES", "PACKAGE_FORMAT", "PACKAGE_PREFIX", "PAYLOAD_NAMES", "VERSION", "Manifest", "Member", "Package", "Transport", "address_manifest", "address_member", "address_member_bytes", "capabilities", "manifest_schema", "package_schema"]
