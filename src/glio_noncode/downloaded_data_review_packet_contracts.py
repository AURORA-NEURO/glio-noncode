"""Typed contracts for source-free downloaded-data review packets."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, hash_bytes

VERSION = "downloaded-data-review-packet-v1"
BOUNDARY = "public_downloaded_data_review_packet"
PACKET_PREFIX = "glio-noncode-download-review-packet"
MANIFEST_PREFIX = PACKET_PREFIX + "-manifest"
MEMBER_PREFIX = PACKET_PREFIX + "-member"
FILE_NAMES = ("manifest.json", "catalog.json", "contract-runtime.json", "runtime-audit.json", "review.md")
PAYLOAD_NAMES = FILE_NAMES[1:]
MEDIA_TYPES = {
    "catalog.json": "application/json",
    "contract-runtime.json": "application/json",
    "runtime-audit.json": "application/json",
    "review.md": "text/markdown",
}
MAX_PACKET_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
ZIP_FORMAT = "zip-stored-utf8-v1"


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


def _bytes(value: Any, field: str, maximum: int) -> bytes:
    if not isinstance(value, bytes) or len(value) > maximum:
        raise ValidationError(f"{field} is outside its byte bound")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its count bound")
    return value


@dataclass(frozen=True)
class DownloadedDataReviewPacketMember:
    relative_path: str
    media_type: str
    byte_count: int
    byte_address: str
    content_address: str

    def __post_init__(self) -> None:
        if self.relative_path not in PAYLOAD_NAMES:
            raise ValidationError("review packet member path is not in the fixed payload set")
        if MEDIA_TYPES[self.relative_path] != self.media_type:
            raise ValidationError("review packet member media type does not replay")
        _count(self.byte_count, "review packet member byte count", MAX_MEMBER_BYTES)
        _address(self.byte_address, "review packet member byte address", MEMBER_PREFIX + "-bytes")
        _address(self.content_address, "review packet member content address", MEMBER_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "byte_address": self.byte_address,
            "content_address": self.content_address,
        }


def address_member(value: DownloadedDataReviewPacketMember) -> str:
    if not isinstance(value, DownloadedDataReviewPacketMember):
        raise ValidationError("review packet member addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


def address_member_bytes(payload: bytes) -> str:
    return hash_bytes(_bytes(payload, "review packet member", MAX_MEMBER_BYTES), prefix=MEMBER_PREFIX + "-bytes")


@dataclass(frozen=True)
class DownloadedDataReviewPacketManifest:
    packet_id: str
    version: str
    boundary: str
    catalog_address: str
    runtime_address: str
    runtime_audit_address: str
    members: tuple[DownloadedDataReviewPacketMember, ...]
    packet_format: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.packet_id, "review packet ID")
        if self.version != VERSION or self.boundary != BOUNDARY or self.packet_format != ZIP_FORMAT:
            raise ValidationError("review packet identity is not current")
        _address(self.catalog_address, "review packet catalog address", "glio-noncode-download-catalog")
        _address(self.runtime_address, "review packet runtime address", "glio-noncode-download-profile-contract-runtime")
        _address(self.runtime_audit_address, "review packet runtime audit address", "glio-noncode-download-profile-contract-runtime-audit")
        if tuple(item.relative_path for item in self.members) != PAYLOAD_NAMES:
            raise ValidationError("review packet payload order is not canonical")
        _address(self.content_address, "review packet manifest address", MANIFEST_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "catalog_address": self.catalog_address,
            "runtime_address": self.runtime_address,
            "runtime_audit_address": self.runtime_audit_address,
            "members": tuple(item.to_dict() for item in self.members),
            "packet_format": self.packet_format,
            "content_address": self.content_address,
        }


def address_manifest(value: DownloadedDataReviewPacketManifest) -> str:
    if not isinstance(value, DownloadedDataReviewPacketManifest):
        raise ValidationError("review packet manifest addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


@dataclass(frozen=True)
class DownloadedDataReviewPacket:
    manifest: DownloadedDataReviewPacketManifest
    packet_bytes: bytes
    packet_address: str

    def __post_init__(self) -> None:
        _bytes(self.packet_bytes, "review packet", MAX_PACKET_BYTES)
        _address(self.packet_address, "review packet address", PACKET_PREFIX)
        if self.manifest.content_address.endswith(":pending"):
            raise ValidationError("review packet manifest must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.manifest.packet_id,
            "version": VERSION,
            "boundary": BOUNDARY,
            "packet_format": self.manifest.packet_format,
            "packet_byte_count": len(self.packet_bytes),
            "packet_address": self.packet_address,
            "manifest": self.manifest.to_dict(),
            "content_address": self.packet_address,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "packet_id": self.manifest.packet_id,
            "version": VERSION,
            "boundary": BOUNDARY,
            "packet_format": self.manifest.packet_format,
            "packet_byte_count": len(self.packet_bytes),
            "packet_address": self.packet_address,
            "member_count": len(self.manifest.members),
            "content_address": self.packet_address,
        }


def address_packet(value: DownloadedDataReviewPacket) -> str:
    if not isinstance(value, DownloadedDataReviewPacket):
        raise ValidationError("review packet addressing requires its typed contract")
    return hash_bytes(value.packet_bytes, prefix=PACKET_PREFIX)


def manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data review packet manifest",
        "type": "object",
        "additionalProperties": False,
        "required": ["packet_id", "version", "boundary", "catalog_address", "runtime_address", "runtime_audit_address", "members", "packet_format", "content_address"],
        "properties": {
            "packet_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "catalog_address": {"type": "string"},
            "runtime_address": {"type": "string"},
            "runtime_audit_address": {"type": "string"},
            "members": {"type": "array", "minItems": len(PAYLOAD_NAMES), "maxItems": len(PAYLOAD_NAMES)},
            "packet_format": {"const": ZIP_FORMAT},
            "content_address": {"type": "string"},
        },
    }


def packet_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data review packet",
        "type": "object",
        "additionalProperties": False,
        "required": ["packet_id", "version", "boundary", "packet_format", "packet_byte_count", "packet_address", "manifest", "content_address"],
        "properties": {
            "packet_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "packet_format": {"const": ZIP_FORMAT},
            "packet_byte_count": {"type": "integer", "minimum": 0},
            "packet_address": {"type": "string"},
            "manifest": manifest_schema(),
            "content_address": {"type": "string"},
        },
    }


def capabilities() -> dict[str, Any]:
    operations = ("build_from_download", "build_packet", "load_source_free", "verify_packet", "query_members", "export_json", "export_csv", "render_markdown", "write_atomic")
    return {"public": True, "independent": True, "source_free_after_build": True, "value_free": True, "version": VERSION, "packet_format": ZIP_FORMAT, "file_count": len(FILE_NAMES), "operation_count": len(operations), "operations": list(operations), "limits": {"max_packet_bytes": MAX_PACKET_BYTES, "max_member_bytes": MAX_MEMBER_BYTES}}


__all__ = [
    "BOUNDARY", "FILE_NAMES", "MAX_MEMBER_BYTES", "MAX_PACKET_BYTES", "MEDIA_TYPES", "MEMBER_PREFIX", "MANIFEST_PREFIX", "PACKET_PREFIX", "PAYLOAD_NAMES", "VERSION", "ZIP_FORMAT",
    "DownloadedDataReviewPacket", "DownloadedDataReviewPacketManifest", "DownloadedDataReviewPacketMember", "address_manifest", "address_member", "address_member_bytes", "address_packet", "capabilities", "manifest_schema", "packet_schema",
]
