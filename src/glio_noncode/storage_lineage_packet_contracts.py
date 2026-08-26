"""Contracts for portable exact-byte storage-lineage packets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_LINEAGE_PACKET_VERSION = "storage-lineage-packet-v1"
STORAGE_LINEAGE_PACKET_SCHEMA_VERSION = "storage-lineage-packet-schema-v1"
STORAGE_LINEAGE_PACKET_BOUNDARY = "public_storage_lineage_packet"
STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT = 10
STORAGE_LINEAGE_PACKET_ARTIFACT_COUNT = STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT + 1
STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS = 24
STORAGE_LINEAGE_PACKET_PAYLOAD_IDS = (
    "graph-json",
    "nodes-csv",
    "edges-csv",
    "summary-json",
    "schema-json",
    "capabilities-json",
    "observability-json",
    "events-csv",
    "review-queue-json",
    "review-csv",
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
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


@dataclass(frozen=True, slots=True)
class StorageLineagePacketArtifact:
    """One fixed UTF-8 payload in a lineage packet."""

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
        return jsonable({
            "artifact_id": self.artifact_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "role": self.role,
            "source_address": self.source_address,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
            "required": self.required,
        })

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        body = self.metadata_dict()
        if include_content:
            body["content"] = self.content.decode("utf-8")
        return body

    def __post_init__(self) -> None:
        _text(self.artifact_id, "lineage_packet_artifact.artifact_id", maximum=160)
        _text(self.relative_path, "lineage_packet_artifact.relative_path", maximum=240)
        _text(self.media_type, "lineage_packet_artifact.media_type", maximum=120)
        _text(self.role, "lineage_packet_artifact.role", maximum=120)
        _text(self.source_address, "lineage_packet_artifact.source_address", maximum=180)
        _int(self.byte_count, "lineage_packet_artifact.byte_count", minimum=0)
        _int(self.line_count, "lineage_packet_artifact.line_count", minimum=0)
        if not isinstance(self.content, bytes):
            raise ValidationError("lineage packet artifact content must be bytes")
        if self.byte_count != len(self.content):
            raise ValidationError("lineage packet artifact byte count does not reconcile")
        _bool(self.required, "lineage_packet_artifact.required")
        _text(self.content_address, "lineage_packet_artifact.content_address", maximum=180)


@dataclass(frozen=True, slots=True)
class StorageLineagePacketManifest:
    """Manifest closing the fixed lineage packet artifact set."""

    version: str
    schema_version: str
    packet_id: str
    graph_address: str
    observability_address: str
    review_address: str
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
            "graph_address": self.graph_address,
            "observability_address": self.observability_address,
            "review_address": self.review_address,
            "artifact_count": self.artifact_count,
            "payload_artifact_count": self.payload_artifact_count,
            "artifacts": self.artifacts,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.version != STORAGE_LINEAGE_PACKET_VERSION:
            raise ValidationError("lineage packet version is invalid")
        if self.schema_version != STORAGE_LINEAGE_PACKET_SCHEMA_VERSION:
            raise ValidationError("lineage packet schema version is invalid")
        _text(self.packet_id, "lineage_packet_manifest.packet_id", maximum=220)
        _text(self.graph_address, "lineage_packet_manifest.graph_address", maximum=180)
        _text(self.observability_address, "lineage_packet_manifest.observability_address", maximum=180)
        _text(self.review_address, "lineage_packet_manifest.review_address", maximum=180)
        _int(self.artifact_count, "lineage_packet_manifest.artifact_count", minimum=1, maximum=STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS)
        _int(self.payload_artifact_count, "lineage_packet_manifest.payload_artifact_count", minimum=1, maximum=STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS)
        if self.artifact_count != self.payload_artifact_count + 1:
            raise ValidationError("lineage packet artifact counts do not reconcile")
        if len(self.artifacts) != self.payload_artifact_count:
            raise ValidationError("lineage packet artifact metadata does not reconcile")
        _bool(self.accepted, "lineage_packet_manifest.accepted")
        expected = _address(self._body(), "storage-lineage-packet-manifest")
        if self.content_address != expected:
            raise ValidationError("lineage packet manifest address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineagePacketManifest:
        body = _mapping(value, "lineage packet manifest")
        allowed = {
            "version", "schema_version", "packet_id", "graph_address", "observability_address",
            "review_address", "artifact_count", "payload_artifact_count", "artifacts",
            "accepted", "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"lineage packet manifest contains unsupported fields: {sorted(unknown)}")
        raw_artifacts = body.get("artifacts")
        if not isinstance(raw_artifacts, (list, tuple)):
            raise ValidationError("lineage packet manifest artifacts must be an array")
        return cls(
            version=_text(body.get("version"), "lineage_packet_manifest.version"),
            schema_version=_text(body.get("schema_version"), "lineage_packet_manifest.schema_version"),
            packet_id=_text(body.get("packet_id"), "lineage_packet_manifest.packet_id", maximum=220),
            graph_address=_text(body.get("graph_address"), "lineage_packet_manifest.graph_address", maximum=180),
            observability_address=_text(body.get("observability_address"), "lineage_packet_manifest.observability_address", maximum=180),
            review_address=_text(body.get("review_address"), "lineage_packet_manifest.review_address", maximum=180),
            artifact_count=_int(body.get("artifact_count"), "lineage_packet_manifest.artifact_count", minimum=1, maximum=STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS),
            payload_artifact_count=_int(body.get("payload_artifact_count"), "lineage_packet_manifest.payload_artifact_count", minimum=1, maximum=STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS),
            artifacts=tuple(_mapping(item, "lineage packet artifact metadata") for item in raw_artifacts),
            accepted=_bool(body.get("accepted"), "lineage_packet_manifest.accepted"),
            content_address=_text(body.get("content_address"), "lineage_packet_manifest.content_address", maximum=180),
        )


@dataclass(frozen=True, slots=True)
class StorageLineagePacket:
    """A typed, portable graph handoff with no source object bytes."""

    packet_id: str
    graph_address: str
    observability_address: str
    review_address: str
    artifacts: tuple[StorageLineagePacketArtifact, ...]
    manifest: StorageLineagePacketManifest
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "graph_address": self.graph_address,
            "observability_address": self.observability_address,
            "review_address": self.review_address,
            "artifacts": tuple(item.metadata_dict() for item in self.artifacts),
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.packet_id, "lineage_packet.packet_id", maximum=220)
        _text(self.graph_address, "lineage_packet.graph_address", maximum=180)
        _text(self.observability_address, "lineage_packet.observability_address", maximum=180)
        _text(self.review_address, "lineage_packet.review_address", maximum=180)
        if len(self.artifacts) != STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT:
            raise ValidationError("lineage packet payload denominator is not closed")
        if self.manifest.payload_artifact_count != len(self.artifacts):
            raise ValidationError("lineage packet manifest payload count does not reconcile")
        if self.manifest.packet_id != self.packet_id:
            raise ValidationError("lineage packet manifest identity does not reconcile")
        if (self.manifest.graph_address, self.manifest.observability_address, self.manifest.review_address) != (self.graph_address, self.observability_address, self.review_address):
            raise ValidationError("lineage packet source identities do not reconcile")
        _bool(self.accepted, "lineage_packet.accepted")
        _text(self.content_address, "lineage_packet.content_address", maximum=180)
        expected = _address(self._body(), "storage-lineage-packet")
        if self.content_address != expected:
            raise ValidationError("lineage packet content address does not reconcile")

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return jsonable({
            "packet_id": self.packet_id,
            "graph_address": self.graph_address,
            "observability_address": self.observability_address,
            "review_address": self.review_address,
            "artifacts": [item.to_dict(include_content=include_content) for item in self.artifacts],
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        })


@dataclass(frozen=True, slots=True)
class StorageLineagePacketVerification:
    """Exact-byte verification receipt for a packet directory."""

    directory: str
    packet_id: str
    graph_address: str
    observability_address: str
    review_address: str
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
        _text(self.directory, "lineage_packet_verification.directory", maximum=500)
        _text(self.packet_id, "lineage_packet_verification.packet_id", maximum=220) if self.packet_id else None
        _text(self.graph_address, "lineage_packet_verification.graph_address", maximum=180) if self.graph_address else None
        _text(self.observability_address, "lineage_packet_verification.observability_address", maximum=180) if self.observability_address else None
        _text(self.review_address, "lineage_packet_verification.review_address", maximum=180) if self.review_address else None
        _int(self.checked_artifact_count, "lineage_packet_verification.checked_artifact_count", minimum=0, maximum=STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS)
        _bool(self.accepted, "lineage_packet_verification.accepted")
        _text(self.content_address, "lineage_packet_verification.content_address", maximum=180)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StorageLineagePacketOffline:
    """Hydrated address-only projections from a verified packet."""

    packet_id: str
    graph: Any
    observability: Any
    review_queue: Any
    manifest: dict[str, Any]
    verification: StorageLineagePacketVerification
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "lineage_packet_offline.packet_id", maximum=220)
        if not isinstance(self.manifest, dict):
            raise ValidationError("lineage packet offline manifest must be an object")
        if not self.verification.accepted:
            raise ValidationError("lineage packet offline verification must be accepted")
        _text(self.content_address, "lineage_packet_offline.content_address", maximum=180)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE_PACKET") or name.startswith("StorageLineagePacket")
]
