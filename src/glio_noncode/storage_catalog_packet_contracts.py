"""Typed contracts for fixed, independently verifiable catalog packets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .release_assurance_support import artifact_address, line_count
from .serialization import content_hash, jsonable

STORAGE_CATALOG_PACKET_VERSION = "storage-catalog-packet-v1"
STORAGE_CATALOG_PACKET_SCHEMA_VERSION = "storage-catalog-packet-schema-v1"
STORAGE_CATALOG_PACKET_BOUNDARY = "public_storage_catalog_packet"
STORAGE_CATALOG_PACKET_PAYLOAD_COUNT = 10
STORAGE_CATALOG_PACKET_ARTIFACT_COUNT = STORAGE_CATALOG_PACKET_PAYLOAD_COUNT + 1
STORAGE_CATALOG_PACKET_MAX_ARTIFACTS = 24
STORAGE_CATALOG_PACKET_PAYLOAD_IDS = (
    "catalog-json",
    "entries-csv",
    "indexes-csv",
    "summary-json",
    "schema-json",
    "capabilities-json",
    "observability-json",
    "events-csv",
    "metrics-csv",
    "boundary-json",
)


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        raise ValidationError(f"{field} is outside its contract")
    return result


@dataclass(frozen=True, slots=True)
class StorageCatalogPacketArtifact:
    """One required UTF-8 packet artifact and its exact bytes."""

    artifact_id: str
    relative_path: str
    media_type: str
    role: str
    source_address: str
    byte_count: int
    line_count: int
    content_address: str
    content: bytes
    required: bool = True

    def metadata_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "artifact_id": self.artifact_id,
                "relative_path": self.relative_path,
                "media_type": self.media_type,
                "role": self.role,
                "source_address": self.source_address,
                "byte_count": self.byte_count,
                "line_count": self.line_count,
                "content_address": self.content_address,
                "required": self.required,
            }
        )

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        value = self.metadata_dict()
        if include_content:
            value["content"] = self.content.decode("utf-8")
        return value

    def __post_init__(self) -> None:
        _text(self.artifact_id, "catalog_packet_artifact.artifact_id", maximum=160)
        _text(self.relative_path, "catalog_packet_artifact.relative_path", maximum=240)
        _text(self.media_type, "catalog_packet_artifact.media_type", maximum=120)
        _text(self.role, "catalog_packet_artifact.role", maximum=120)
        _text(self.source_address, "catalog_packet_artifact.source_address", maximum=180)
        _int(self.byte_count, "catalog_packet_artifact.byte_count", minimum=0)
        _int(self.line_count, "catalog_packet_artifact.line_count", minimum=0)
        if not isinstance(self.content, bytes):
            raise ValidationError("catalog packet artifact content must be bytes")
        if self.byte_count != len(self.content):
            raise ValidationError("catalog packet artifact byte count does not reconcile")
        if line_count(self.content) != self.line_count:
            raise ValidationError("catalog packet artifact line count does not reconcile")
        if artifact_address(self.content) != self.content_address:
            raise ValidationError("catalog packet artifact content address does not reconcile")
        _bool(self.required, "catalog_packet_artifact.required")


@dataclass(frozen=True, slots=True)
class StorageCatalogPacketManifest:
    """Manifest that closes the fixed catalog packet artifact set."""

    version: str
    schema_version: str
    packet_id: str
    catalog_address: str
    observability_address: str
    artifact_count: int
    payload_artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "schema_version": self.schema_version,
            "packet_id": self.packet_id,
            "catalog_address": self.catalog_address,
            "observability_address": self.observability_address,
            "artifact_count": self.artifact_count,
            "payload_artifact_count": self.payload_artifact_count,
            "artifacts": self.artifacts,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if (
            self.version != STORAGE_CATALOG_PACKET_VERSION
            or self.schema_version != STORAGE_CATALOG_PACKET_SCHEMA_VERSION
        ):
            raise ValidationError("catalog packet manifest version is invalid")
        _text(self.packet_id, "catalog_packet_manifest.packet_id", maximum=220)
        _text(self.catalog_address, "catalog_packet_manifest.catalog_address", maximum=180)
        _text(
            self.observability_address, "catalog_packet_manifest.observability_address", maximum=180
        )
        _int(
            self.artifact_count,
            "catalog_packet_manifest.artifact_count",
            minimum=1,
            maximum=STORAGE_CATALOG_PACKET_MAX_ARTIFACTS,
        )
        _int(
            self.payload_artifact_count,
            "catalog_packet_manifest.payload_artifact_count",
            minimum=1,
            maximum=STORAGE_CATALOG_PACKET_MAX_ARTIFACTS,
        )
        if (
            self.artifact_count != self.payload_artifact_count + 1
            or len(self.artifacts) != self.payload_artifact_count
        ):
            raise ValidationError("catalog packet manifest artifact counts do not reconcile")
        _bool(self.accepted, "catalog_packet_manifest.accepted")
        if self.content_address != content_hash(
            self._body(), prefix="storage-catalog-packet-manifest"
        ):
            raise ValidationError("catalog packet manifest address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalogPacketManifest:
        body = _mapping(value, "catalog packet manifest")
        allowed = {
            "version",
            "schema_version",
            "packet_id",
            "catalog_address",
            "observability_address",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"catalog packet manifest contains unsupported fields: {sorted(unknown)}"
            )
        rows = body.get("artifacts")
        if not isinstance(rows, (list, tuple)):
            raise ValidationError("catalog packet manifest artifacts must be an array")
        return cls(
            version=_text(body.get("version"), "catalog_packet_manifest.version"),
            schema_version=_text(
                body.get("schema_version"), "catalog_packet_manifest.schema_version"
            ),
            packet_id=_text(
                body.get("packet_id"), "catalog_packet_manifest.packet_id", maximum=220
            ),
            catalog_address=_text(
                body.get("catalog_address"), "catalog_packet_manifest.catalog_address", maximum=180
            ),
            observability_address=_text(
                body.get("observability_address"),
                "catalog_packet_manifest.observability_address",
                maximum=180,
            ),
            artifact_count=_int(
                body.get("artifact_count"),
                "catalog_packet_manifest.artifact_count",
                minimum=1,
                maximum=STORAGE_CATALOG_PACKET_MAX_ARTIFACTS,
            ),
            payload_artifact_count=_int(
                body.get("payload_artifact_count"),
                "catalog_packet_manifest.payload_artifact_count",
                minimum=1,
                maximum=STORAGE_CATALOG_PACKET_MAX_ARTIFACTS,
            ),
            artifacts=tuple(_mapping(item, "catalog packet artifact metadata") for item in rows),
            accepted=_bool(body.get("accepted"), "catalog_packet_manifest.accepted"),
            content_address=_text(
                body.get("content_address"), "catalog_packet_manifest.content_address", maximum=180
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageCatalogPacket:
    """Portable catalog handoff with fixed payload bytes held in memory."""

    packet_id: str
    catalog_address: str
    observability_address: str
    artifacts: tuple[StorageCatalogPacketArtifact, ...]
    manifest: StorageCatalogPacketManifest
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "catalog_address": self.catalog_address,
            "observability_address": self.observability_address,
            "artifacts": tuple(item.metadata_dict() for item in self.artifacts),
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.packet_id, "catalog_packet.packet_id", maximum=220)
        _text(self.catalog_address, "catalog_packet.catalog_address", maximum=180)
        _text(self.observability_address, "catalog_packet.observability_address", maximum=180)
        if len(
            self.artifacts
        ) != STORAGE_CATALOG_PACKET_PAYLOAD_COUNT or self.manifest.payload_artifact_count != len(
            self.artifacts
        ):
            raise ValidationError("catalog packet payload denominator is not closed")
        if self.manifest.packet_id != self.packet_id or (
            self.manifest.catalog_address,
            self.manifest.observability_address,
        ) != (self.catalog_address, self.observability_address):
            raise ValidationError("catalog packet source identity does not reconcile")
        if tuple(item.artifact_id for item in self.artifacts) != STORAGE_CATALOG_PACKET_PAYLOAD_IDS:
            raise ValidationError("catalog packet payload IDs are not closed")
        _bool(self.accepted, "catalog_packet.accepted")
        if self.content_address != content_hash(self._body(), prefix="storage-catalog-packet"):
            raise ValidationError("catalog packet address does not reconcile")

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return jsonable(
            {
                "packet_id": self.packet_id,
                "catalog_address": self.catalog_address,
                "observability_address": self.observability_address,
                "artifacts": [
                    item.to_dict(include_content=include_content) for item in self.artifacts
                ],
                "manifest": self.manifest.to_dict(),
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


@dataclass(frozen=True, slots=True)
class StorageCatalogPacketVerification:
    """Exact-byte packet-directory verification receipt."""

    directory: str
    packet_id: str
    catalog_address: str
    observability_address: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    tampered_paths: tuple[str, ...]
    duplicate_paths: tuple[str, ...]
    manifest_drift: tuple[str, ...]
    boundary_violations: tuple[str, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.directory, "catalog_packet_verification.directory", maximum=500)
        _int(
            self.checked_artifact_count,
            "catalog_packet_verification.checked_artifact_count",
            minimum=0,
            maximum=STORAGE_CATALOG_PACKET_MAX_ARTIFACTS,
        )
        _bool(self.accepted, "catalog_packet_verification.accepted")
        if self.content_address != content_hash(
            {key: value for key, value in jsonable(self).items() if key != "content_address"},
            prefix="storage-catalog-packet-verification",
        ):
            raise ValidationError("catalog packet verification address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StorageCatalogPacketOffline:
    """Hydrated catalog and observation projections after verification."""

    packet_id: str
    catalog: Any
    observability: Any
    manifest: dict[str, Any]
    verification: StorageCatalogPacketVerification
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "catalog_packet_offline.packet_id", maximum=220)
        if not isinstance(self.manifest, dict) or not self.verification.accepted:
            raise ValidationError("catalog packet offline state is invalid")
        _text(self.content_address, "catalog_packet_offline.content_address", maximum=180)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_CATALOG_PACKET") or name.startswith("StorageCatalogPacket")
]
