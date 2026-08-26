"""Contracts for exact-byte storage maintenance plan handoffs.

The planner is useful locally, but review needs a durable artifact that can be
verified without reopening the source store. This module defines a fixed
payload set, manifest, verification receipt, and offline hydration value. The
payloads contain plan metadata and aggregate action rows; source object bytes
never enter the packet.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_MAINTENANCE_PACKET_VERSION = "storage-maintenance-packet-v1"
STORAGE_MAINTENANCE_PACKET_SCHEMA_VERSION = "storage-maintenance-packet-schema-v1"
STORAGE_MAINTENANCE_PACKET_BOUNDARY = "public_storage_maintenance_packet"
STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT = 7
STORAGE_MAINTENANCE_PACKET_ARTIFACT_COUNT = 8
STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS = 16
STORAGE_MAINTENANCE_PACKET_PAYLOAD_IDS = (
    "plan-json",
    "actions-csv",
    "summary-json",
    "schema-json",
    "capabilities-json",
    "observability-json",
    "review-queue-json",
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
class StorageMaintenancePacketArtifact:
    """One required UTF-8 payload in a maintenance packet."""

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
        body = self.metadata_dict()
        if include_content:
            body["content"] = self.content.decode("utf-8")
        return body

    def __post_init__(self) -> None:
        _text(self.artifact_id, "maintenance_packet_artifact.artifact_id", maximum=160)
        _text(self.relative_path, "maintenance_packet_artifact.relative_path", maximum=240)
        _text(self.media_type, "maintenance_packet_artifact.media_type", maximum=120)
        _text(self.role, "maintenance_packet_artifact.role", maximum=120)
        _text(self.source_address, "maintenance_packet_artifact.source_address")
        _int(self.byte_count, "maintenance_packet_artifact.byte_count", minimum=0)
        _int(self.line_count, "maintenance_packet_artifact.line_count", minimum=0)
        if not isinstance(self.content, bytes):
            raise ValidationError("maintenance packet artifact content must be bytes")
        if self.byte_count != len(self.content):
            raise ValidationError("maintenance packet artifact byte count does not reconcile")
        _bool(self.required, "maintenance_packet_artifact.required")
        _text(self.content_address, "maintenance_packet_artifact.content_address")


@dataclass(frozen=True, slots=True)
class StorageMaintenancePacketManifest:
    """Manifest that closes the fixed maintenance packet artifact set."""

    version: str
    schema_version: str
    packet_id: str
    plan_id: str
    plan_address: str
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
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "artifact_count": self.artifact_count,
            "payload_artifact_count": self.payload_artifact_count,
            "artifacts": self.artifacts,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.version != STORAGE_MAINTENANCE_PACKET_VERSION:
            raise ValidationError("maintenance packet version is invalid")
        if self.schema_version != STORAGE_MAINTENANCE_PACKET_SCHEMA_VERSION:
            raise ValidationError("maintenance packet schema version is invalid")
        _text(self.packet_id, "maintenance_packet_manifest.packet_id", maximum=220)
        _text(self.plan_id, "maintenance_packet_manifest.plan_id", maximum=180)
        _text(self.plan_address, "maintenance_packet_manifest.plan_address", maximum=180)
        _int(
            self.artifact_count,
            "maintenance_packet_manifest.artifact_count",
            minimum=1,
            maximum=STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS,
        )
        _int(
            self.payload_artifact_count,
            "maintenance_packet_manifest.payload_artifact_count",
            minimum=1,
            maximum=STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS,
        )
        if self.artifact_count != self.payload_artifact_count + 1:
            raise ValidationError("maintenance packet artifact counts do not reconcile")
        if len(self.artifacts) != self.payload_artifact_count:
            raise ValidationError("maintenance packet artifact metadata does not reconcile")
        _bool(self.accepted, "maintenance_packet_manifest.accepted")
        expected = _address(self._body(), "storage-maintenance-packet-manifest")
        if self.content_address != expected:
            raise ValidationError("maintenance packet manifest address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenancePacketManifest:
        body = _mapping(value, "maintenance packet manifest")
        allowed = {
            "version",
            "schema_version",
            "packet_id",
            "plan_id",
            "plan_address",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance packet manifest contains unsupported fields: {sorted(unknown)}"
            )
        raw_artifacts = body.get("artifacts")
        if not isinstance(raw_artifacts, (list, tuple)):
            raise ValidationError("maintenance packet manifest artifacts must be an array")
        artifacts = tuple(
            _mapping(item, "maintenance packet artifact metadata") for item in raw_artifacts
        )
        return cls(
            version=_text(body.get("version"), "maintenance_packet_manifest.version"),
            schema_version=_text(
                body.get("schema_version"), "maintenance_packet_manifest.schema_version"
            ),
            packet_id=_text(
                body.get("packet_id"), "maintenance_packet_manifest.packet_id", maximum=220
            ),
            plan_id=_text(body.get("plan_id"), "maintenance_packet_manifest.plan_id", maximum=180),
            plan_address=_text(
                body.get("plan_address"), "maintenance_packet_manifest.plan_address", maximum=180
            ),
            artifact_count=_int(
                body.get("artifact_count"),
                "maintenance_packet_manifest.artifact_count",
                minimum=1,
                maximum=STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS,
            ),
            payload_artifact_count=_int(
                body.get("payload_artifact_count"),
                "maintenance_packet_manifest.payload_artifact_count",
                minimum=1,
                maximum=STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS,
            ),
            artifacts=artifacts,
            accepted=_bool(body.get("accepted"), "maintenance_packet_manifest.accepted"),
            content_address=_text(
                body.get("content_address"), "maintenance_packet_manifest.content_address"
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageMaintenancePacket:
    """Fixed payload packet for an addressed maintenance plan."""

    packet_id: str
    plan_id: str
    plan_address: str
    artifacts: tuple[StorageMaintenancePacketArtifact, ...]
    manifest: StorageMaintenancePacketManifest
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "artifacts": tuple(item.metadata_dict() for item in self.artifacts),
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.packet_id, "maintenance_packet.packet_id", maximum=220)
        _text(self.plan_id, "maintenance_packet.plan_id", maximum=180)
        _text(self.plan_address, "maintenance_packet.plan_address", maximum=180)
        if len(self.artifacts) != STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT:
            raise ValidationError("maintenance packet payload denominator is not closed")
        if self.manifest.payload_artifact_count != len(self.artifacts):
            raise ValidationError("maintenance packet manifest payload count does not reconcile")
        if self.manifest.packet_id != self.packet_id or self.manifest.plan_id != self.plan_id:
            raise ValidationError("maintenance packet manifest identity does not reconcile")
        if self.manifest.plan_address != self.plan_address:
            raise ValidationError("maintenance packet plan address does not reconcile")
        _bool(self.accepted, "maintenance_packet.accepted")
        _text(self.content_address, "maintenance_packet.content_address")
        expected = _address(self._body(), "storage-maintenance-packet")
        if self.content_address != expected:
            raise ValidationError("maintenance packet content address does not reconcile")

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return jsonable(
            {
                "packet_id": self.packet_id,
                "plan_id": self.plan_id,
                "plan_address": self.plan_address,
                "artifacts": [
                    item.to_dict(include_content=include_content) for item in self.artifacts
                ],
                "manifest": self.manifest.to_dict(),
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


@dataclass(frozen=True, slots=True)
class StorageMaintenancePacketVerification:
    """Deterministic exact-byte verification receipt."""

    directory: str
    packet_id: str
    plan_id: str
    plan_address: str
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
        _text(self.directory, "maintenance_packet_verification.directory", maximum=500)
        _int(
            self.checked_artifact_count,
            "maintenance_packet_verification.checked_artifact_count",
            minimum=0,
            maximum=STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS,
        )
        _bool(self.accepted, "maintenance_packet_verification.accepted")
        _text(self.content_address, "maintenance_packet_verification.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StorageMaintenancePacketOffline:
    """Hydrated plan and verification receipt from a verified directory."""

    packet_id: str
    plan: Any
    manifest: dict[str, Any]
    verification: StorageMaintenancePacketVerification
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "maintenance_packet_offline.packet_id", maximum=220)
        if not isinstance(self.manifest, dict):
            raise ValidationError("maintenance packet offline manifest must be an object")
        _text(self.content_address, "maintenance_packet_offline.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_MAINTENANCE_PACKET") or name.startswith("StorageMaintenancePacket")
]
