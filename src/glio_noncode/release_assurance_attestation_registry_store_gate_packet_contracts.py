"""Contracts for exact-byte offline promotion-gate packets.

The store packet carries operational history.  This packet carries the release
decision made over that history.  Keeping the two handoffs separate lets a
consumer archive or review a gate without receiving source attestation
payloads, while the manifest still binds the gate, store, and registry
addresses into one portable value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_VERSION = (
    "release-assurance-attestation-registry-store-gate-packet-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_SCHEMA_VERSION = (
    "release-assurance-attestation-registry-store-gate-packet-schema-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_BOUNDARY = (
    "public_release_registry_store_gate_packet"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT = 6
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_ARTIFACT_COUNT = 7
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS = 24
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS = (
    "gate-json",
    "checks-csv",
    "policy-json",
    "summary-json",
    "schema-json",
    "capabilities-json",
)


def _text(value: Any, field: str, *, maximum: int = 240) -> str:
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
class ReleaseAssuranceAttestationRegistryStoreGatePacketArtifact:
    """One fixed public payload in a gate packet."""

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
        _text(self.artifact_id, "gate_packet_artifact.artifact_id", maximum=160)
        _text(self.relative_path, "gate_packet_artifact.relative_path", maximum=240)
        _text(self.media_type, "gate_packet_artifact.media_type", maximum=120)
        _text(self.role, "gate_packet_artifact.role", maximum=120)
        _text(self.source_address, "gate_packet_artifact.source_address")
        _int(self.byte_count, "gate_packet_artifact.byte_count", minimum=0)
        _int(self.line_count, "gate_packet_artifact.line_count", minimum=0)
        if not isinstance(self.content, bytes):
            raise ValidationError("gate packet artifact content must be bytes")
        if self.byte_count != len(self.content):
            raise ValidationError("gate packet artifact byte count does not reconcile")
        _bool(self.required, "gate_packet_artifact.required")
        _text(self.content_address, "gate_packet_artifact.content_address")


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGatePacketManifest:
    version: str
    schema_version: str
    packet_id: str
    gate_id: str
    store_id: str
    registry_id: str
    gate_address: str
    artifact_count: int
    payload_artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    source_addresses: tuple[tuple[str, str], ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "schema_version": self.schema_version,
            "packet_id": self.packet_id,
            "gate_id": self.gate_id,
            "store_id": self.store_id,
            "registry_id": self.registry_id,
            "gate_address": self.gate_address,
            "artifact_count": self.artifact_count,
            "payload_artifact_count": self.payload_artifact_count,
            "artifacts": self.artifacts,
            "source_addresses": self.source_addresses,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_VERSION:
            raise ValidationError("gate packet version is invalid")
        if (
            self.schema_version
            != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_SCHEMA_VERSION
        ):
            raise ValidationError("gate packet schema version is invalid")
        _text(self.packet_id, "gate_packet_manifest.packet_id", maximum=220)
        _text(self.gate_id, "gate_packet_manifest.gate_id", maximum=180)
        _text(self.store_id, "gate_packet_manifest.store_id", maximum=180)
        _text(self.registry_id, "gate_packet_manifest.registry_id", maximum=180)
        _text(self.gate_address, "gate_packet_manifest.gate_address")
        _int(
            self.artifact_count,
            "gate_packet_manifest.artifact_count",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS,
        )
        _int(
            self.payload_artifact_count,
            "gate_packet_manifest.payload_artifact_count",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS,
        )
        if self.artifact_count != self.payload_artifact_count + 1:
            raise ValidationError("gate packet artifact counts do not reconcile")
        if len(self.artifacts) != self.payload_artifact_count:
            raise ValidationError("gate packet artifact metadata does not reconcile")
        _bool(self.accepted, "gate_packet_manifest.accepted")
        _text(self.content_address, "gate_packet_manifest.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
    ) -> ReleaseAssuranceAttestationRegistryStoreGatePacketManifest:
        body = _mapping(value, "gate packet manifest")
        allowed = {
            "version",
            "schema_version",
            "packet_id",
            "gate_id",
            "store_id",
            "registry_id",
            "gate_address",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "source_addresses",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"gate packet manifest contains unsupported fields: {sorted(unknown)}"
            )
        raw_artifacts = body.get("artifacts")
        raw_sources = body.get("source_addresses")
        if not isinstance(raw_artifacts, (list, tuple)):
            raise ValidationError("gate packet manifest artifacts must be an array")
        if not isinstance(raw_sources, (list, tuple)):
            raise ValidationError("gate packet manifest source addresses must be an array")
        artifacts = tuple(_mapping(item, "gate packet artifact metadata") for item in raw_artifacts)
        source_addresses = tuple(
            (str(item[0]), str(item[1]))
            for item in raw_sources
            if isinstance(item, (list, tuple)) and len(item) == 2
        )
        manifest = cls(
            version=_text(body.get("version"), "gate_packet_manifest.version"),
            schema_version=_text(body.get("schema_version"), "gate_packet_manifest.schema_version"),
            packet_id=_text(body.get("packet_id"), "gate_packet_manifest.packet_id", maximum=220),
            gate_id=_text(body.get("gate_id"), "gate_packet_manifest.gate_id", maximum=180),
            store_id=_text(body.get("store_id"), "gate_packet_manifest.store_id", maximum=180),
            registry_id=_text(
                body.get("registry_id"), "gate_packet_manifest.registry_id", maximum=180
            ),
            gate_address=_text(body.get("gate_address"), "gate_packet_manifest.gate_address"),
            artifact_count=_int(
                body.get("artifact_count"),
                "gate_packet_manifest.artifact_count",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS,
            ),
            payload_artifact_count=_int(
                body.get("payload_artifact_count"),
                "gate_packet_manifest.payload_artifact_count",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS,
            ),
            artifacts=artifacts,
            source_addresses=source_addresses,
            accepted=_bool(body.get("accepted"), "gate_packet_manifest.accepted"),
            content_address=_text(
                body.get("content_address"), "gate_packet_manifest.content_address"
            ),
        )
        if (
            _address(manifest._body(), "release-assurance-attestation-registry-store-gate-manifest")
            != manifest.content_address
        ):
            raise ValidationError("gate packet manifest content address does not reconcile")
        return manifest


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGatePacket:
    packet_id: str
    gate_id: str
    store_id: str
    registry_id: str
    artifacts: tuple[ReleaseAssuranceAttestationRegistryStoreGatePacketArtifact, ...]
    manifest: ReleaseAssuranceAttestationRegistryStoreGatePacketManifest
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "gate_packet.packet_id", maximum=220)
        _text(self.gate_id, "gate_packet.gate_id", maximum=180)
        _text(self.store_id, "gate_packet.store_id", maximum=180)
        _text(self.registry_id, "gate_packet.registry_id", maximum=180)
        if (
            len(self.artifacts)
            != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT
        ):
            raise ValidationError("gate packet payload denominator is not closed")
        if self.manifest.payload_artifact_count != len(self.artifacts):
            raise ValidationError("gate packet manifest payload count does not reconcile")
        if self.manifest.gate_id != self.gate_id or self.manifest.gate_address == "":
            raise ValidationError("gate packet manifest identity does not reconcile")
        _bool(self.accepted, "gate_packet.accepted")
        _text(self.content_address, "gate_packet.content_address")

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        body = {
            "packet_id": self.packet_id,
            "gate_id": self.gate_id,
            "store_id": self.store_id,
            "registry_id": self.registry_id,
            "artifacts": [item.to_dict(include_content=include_content) for item in self.artifacts],
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        return jsonable(body)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGatePacketVerification:
    directory: str
    packet_id: str
    gate_id: str
    store_id: str
    registry_id: str
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
        _text(self.directory, "gate_packet_verification.directory", maximum=500)
        _text(self.packet_id or "empty", "gate_packet_verification.packet_id", maximum=220)
        _text(self.gate_id or "empty", "gate_packet_verification.gate_id", maximum=180)
        _text(self.store_id or "empty", "gate_packet_verification.store_id", maximum=180)
        _text(self.registry_id or "empty", "gate_packet_verification.registry_id", maximum=180)
        _int(
            self.checked_artifact_count,
            "gate_packet_verification.checked_artifact_count",
            minimum=0,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS,
        )
        _bool(self.accepted, "gate_packet_verification.accepted")
        _text(self.content_address, "gate_packet_verification.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGatePacketOffline:
    packet_id: str
    gate: Any
    manifest: dict[str, Any]
    verification: ReleaseAssuranceAttestationRegistryStoreGatePacketVerification
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "gate_packet_offline.packet_id", maximum=220)
        if not isinstance(self.manifest, dict):
            raise ValidationError("gate packet offline manifest must be an object")
        _text(self.content_address, "gate_packet_offline.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET")
    or name.startswith("ReleaseAssuranceAttestationRegistryStoreGatePacket")
]
