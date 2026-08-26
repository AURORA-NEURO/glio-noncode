"""Contracts for exact-byte offline module-impact packets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import jsonable

MODULE_IMPACT_PACKET_VERSION = "module-impact-packet-v1"
MODULE_IMPACT_PACKET_BOUNDARY = "public_aggregate_module_impact_packet"
MODULE_IMPACT_PACKET_MANIFEST = "manifest.json"
MODULE_IMPACT_PACKET_ARTIFACT_COUNT = 10
MODULE_IMPACT_PACKET_ARTIFACT_PREFIX = "module-impact-packet-artifact"


class ModuleImpactPacketState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleImpactPacketArtifactKind(StrEnum):
    LEFT_INVENTORY = "left_inventory"
    RIGHT_INVENTORY = "right_inventory"
    DIFF = "diff"
    IMPACTS = "impacts"
    VERIFICATION = "verification"
    GATE = "gate"
    AUDIT = "audit"
    RUNTIME = "runtime"
    OBSERVABILITY = "observability"
    SUMMARY = "summary"


class ModuleImpactPacketCheckPlane(StrEnum):
    PATH = "path"
    BYTES = "bytes"
    MANIFEST = "manifest"
    PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class ModuleImpactPacketArtifact:
    """One UTF-8 packet artifact addressed by exact bytes."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: ModuleImpactPacketArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in ("artifact_id", "relative_path", "media_type", "content_address")
        ):
            raise ValidationError("module impact packet artifact identifiers are required")
        if (
            self.relative_path.startswith("/")
            or "\\" in self.relative_path
            or ".." in self.relative_path
        ):
            raise ValidationError("module impact packet artifact path is unsafe")
        if self.byte_count < 0 or self.line_count < 0:
            raise ValidationError("module impact packet artifact counters cannot be negative")

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result = jsonable(self)
        if not include_payload:
            result.pop("payload", None)
        return result


@dataclass(frozen=True, slots=True)
class ModuleImpactPacketCheck:
    """One packet verification finding."""

    check_id: str
    plane: ModuleImpactPacketCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in ("check_id", "detail", "content_address")
        ):
            raise ValidationError("module impact packet check is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleImpactPacketVerification:
    """Filesystem verification result that remains inspectable when blocked."""

    packet_id: str
    checks: tuple[ModuleImpactPacketCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.packet_id.strip() or not self.content_address.strip() or not self.checks:
            raise ValidationError("module impact packet verification is incomplete")

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
class ModuleImpactPacket:
    """Ten-artifact offline closure for change impact review."""

    packet_id: str
    version: str
    boundary: str
    left_inventory_address: str
    right_inventory_address: str
    diff_address: str
    impact_address: str
    gate_address: str
    runtime_address: str
    state: ModuleImpactPacketState
    accepted: bool
    artifacts: tuple[ModuleImpactPacketArtifact, ...]
    checks: tuple[ModuleImpactPacketCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in (
                "packet_id",
                "version",
                "left_inventory_address",
                "right_inventory_address",
                "diff_address",
                "impact_address",
                "gate_address",
                "runtime_address",
                "content_address",
            )
        ):
            raise ValidationError("module impact packet identifiers are required")
        if self.boundary != MODULE_IMPACT_PACKET_BOUNDARY:
            raise ValidationError("module impact packet boundary is invalid")
        if len(self.artifacts) != MODULE_IMPACT_PACKET_ARTIFACT_COUNT:
            raise ValidationError("module impact packet artifact count is invalid")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValidationError("module impact packet artifact IDs must be unique")
        if not self.checks:
            raise ValidationError("module impact packet requires checks")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("module impact packet acceptance must conserve checks")
        if (self.state is ModuleImpactPacketState.ACCEPTED) != self.accepted:
            raise ValidationError("module impact packet state must match acceptance")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "left_inventory_address": self.left_inventory_address,
            "right_inventory_address": self.right_inventory_address,
            "diff_address": self.diff_address,
            "impact_address": self.impact_address,
            "gate_address": self.gate_address,
            "runtime_address": self.runtime_address,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_count": self.artifact_count,
            "artifacts": [
                item.to_dict(include_payload=include_payloads) for item in self.artifacts
            ],
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


__all__ = [
    "MODULE_IMPACT_PACKET_ARTIFACT_COUNT",
    "MODULE_IMPACT_PACKET_ARTIFACT_PREFIX",
    "MODULE_IMPACT_PACKET_BOUNDARY",
    "MODULE_IMPACT_PACKET_MANIFEST",
    "MODULE_IMPACT_PACKET_VERSION",
    "ModuleImpactPacket",
    "ModuleImpactPacketArtifact",
    "ModuleImpactPacketArtifactKind",
    "ModuleImpactPacketCheck",
    "ModuleImpactPacketCheckPlane",
    "ModuleImpactPacketState",
    "ModuleImpactPacketVerification",
]
