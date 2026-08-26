"""Contracts for the exact-byte module inventory handoff packet."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import jsonable

MODULE_INVENTORY_PACKET_VERSION = "module-inventory-packet-v1"
MODULE_INVENTORY_PACKET_BOUNDARY = "public_aggregate_module_inventory_packet"
MODULE_INVENTORY_PACKET_MANIFEST = "manifest.json"
MODULE_INVENTORY_PACKET_ARTIFACT_COUNT = 10
MODULE_INVENTORY_PACKET_ARTIFACT_PREFIX = "module-inventory-packet-artifact"


class ModuleInventoryPacketState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleInventoryPacketArtifactKind(StrEnum):
    INVENTORY = "inventory"
    GRAPH = "graph"
    MODULES = "modules"
    SYMBOLS = "symbols"
    DEPENDENCIES = "dependencies"
    INDEXES = "indexes"
    SUMMARY = "summary"
    AUDIT = "audit"
    RUNTIME = "runtime"


class ModuleInventoryPacketCheckPlane(StrEnum):
    PATH = "path"
    BYTES = "bytes"
    MANIFEST = "manifest"
    PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class ModuleInventoryPacketArtifact:
    """One UTF-8 artifact addressed by exact bytes."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: ModuleInventoryPacketArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.artifact_id.strip()
            or not self.relative_path.strip()
            or not self.media_type.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("module inventory packet artifact identifiers are required")
        if (
            self.relative_path.startswith("/")
            or "\\" in self.relative_path
            or ".." in self.relative_path
        ):
            raise ValidationError("module inventory packet artifact path is unsafe")
        if self.byte_count < 0 or self.line_count < 0:
            raise ValidationError("module inventory packet artifact counts cannot be negative")

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result = jsonable(self)
        if not include_payload:
            result.pop("payload", None)
        return result


@dataclass(frozen=True, slots=True)
class ModuleInventoryPacketCheck:
    """One packet verification finding."""

    check_id: str
    plane: ModuleInventoryPacketCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.detail.strip() or not self.content_address.strip():
            raise ValidationError("module inventory packet check identifiers are required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryPacketVerification:
    """Filesystem verification result that remains inspectable when blocked."""

    packet_id: str
    checks: tuple[ModuleInventoryPacketCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.packet_id.strip() or not self.content_address.strip() or not self.checks:
            raise ValidationError("module inventory packet verification is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleInventoryPacket:
    """Ten-artifact portable handoff for offline module review."""

    packet_id: str
    version: str
    boundary: str
    inventory_address: str
    runtime_address: str
    state: ModuleInventoryPacketState
    accepted: bool
    artifacts: tuple[ModuleInventoryPacketArtifact, ...]
    checks: tuple[ModuleInventoryPacketCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.packet_id.strip()
            or not self.version.strip()
            or not self.inventory_address.strip()
            or not self.runtime_address.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("module inventory packet identifiers are required")
        if self.boundary != MODULE_INVENTORY_PACKET_BOUNDARY:
            raise ValidationError("module inventory packet boundary is invalid")
        if len(self.artifacts) != MODULE_INVENTORY_PACKET_ARTIFACT_COUNT:
            raise ValidationError("module inventory packet artifact count is invalid")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValidationError("module inventory packet artifact identifiers must be unique")
        if not self.checks:
            raise ValidationError("module inventory packet requires checks")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "inventory_address": self.inventory_address,
            "runtime_address": self.runtime_address,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_count": len(self.artifacts),
            "artifacts": [
                item.to_dict(include_payload=include_payloads) for item in self.artifacts
            ],
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


__all__ = [
    "MODULE_INVENTORY_PACKET_ARTIFACT_COUNT",
    "MODULE_INVENTORY_PACKET_ARTIFACT_PREFIX",
    "MODULE_INVENTORY_PACKET_BOUNDARY",
    "MODULE_INVENTORY_PACKET_MANIFEST",
    "MODULE_INVENTORY_PACKET_VERSION",
    "ModuleInventoryPacket",
    "ModuleInventoryPacketArtifact",
    "ModuleInventoryPacketArtifactKind",
    "ModuleInventoryPacketCheck",
    "ModuleInventoryPacketCheckPlane",
    "ModuleInventoryPacketState",
    "ModuleInventoryPacketVerification",
]
