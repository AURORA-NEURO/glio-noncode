"""Contracts for exact-byte offline module certification packets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import jsonable

MODULE_CERTIFICATION_PACKET_VERSION = "module-certification-packet-v1"
MODULE_CERTIFICATION_PACKET_BOUNDARY = "public_aggregate_module_certification_packet"
MODULE_CERTIFICATION_PACKET_MANIFEST = "manifest.json"
MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT = 10
MODULE_CERTIFICATION_PACKET_ARTIFACT_PREFIX = "module-certification-packet-artifact"


class ModuleCertificationPacketState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleCertificationPacketArtifactKind(StrEnum):
    MATRIX = "matrix"
    CHECKS = "checks"
    GAPS = "gaps"
    TASKS = "tasks"
    TASKS_TABLE = "tasks_table"
    GATE = "gate"
    AUDIT = "audit"
    RUNTIME = "runtime"
    OBSERVABILITY = "observability"
    SUMMARY = "summary"


class ModuleCertificationPacketCheckPlane(StrEnum):
    PATH = "path"
    BYTES = "bytes"
    MANIFEST = "manifest"
    LINK = "link"
    PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class ModuleCertificationPacketArtifact:
    """One UTF-8 packet artifact addressed by exact bytes."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: ModuleCertificationPacketArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in ("artifact_id", "relative_path", "media_type", "content_address")
        ):
            raise ValidationError("certification packet artifact identifiers are required")
        if (
            self.relative_path.startswith("/")
            or "\\" in self.relative_path
            or ".." in self.relative_path
        ):
            raise ValidationError("certification packet artifact path is unsafe")
        if self.byte_count < 0 or self.line_count < 0:
            raise ValidationError("certification packet artifact counts cannot be negative")

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result = jsonable(self)
        if not include_payload:
            result.pop("payload", None)
        return result


@dataclass(frozen=True, slots=True)
class ModuleCertificationPacketCheck:
    """One packet verification check."""

    check_id: str
    plane: ModuleCertificationPacketCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("check_id", "detail", "content_address"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValidationError("certification packet check identifiers are required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationPacketVerification:
    """Offline verification result that remains inspectable when blocked."""

    packet_id: str
    checks: tuple[ModuleCertificationPacketCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.packet_id.strip() or not self.content_address.strip() or not self.checks:
            raise ValidationError("certification packet verification is incomplete")

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
class ModuleCertificationPacket:
    """Ten-artifact portable handoff for module certification review."""

    packet_id: str
    version: str
    boundary: str
    matrix_address: str
    gate_address: str
    runtime_address: str
    state: ModuleCertificationPacketState
    accepted: bool
    artifacts: tuple[ModuleCertificationPacketArtifact, ...]
    checks: tuple[ModuleCertificationPacketCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in (
                "packet_id",
                "version",
                "matrix_address",
                "gate_address",
                "runtime_address",
                "content_address",
            )
        ):
            raise ValidationError("certification packet identifiers are required")
        if self.boundary != MODULE_CERTIFICATION_PACKET_BOUNDARY:
            raise ValidationError("certification packet boundary is invalid")
        if len(self.artifacts) != MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT:
            raise ValidationError("certification packet artifact count is invalid")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValidationError("certification packet artifact IDs must be unique")
        if not self.checks:
            raise ValidationError("certification packet requires checks")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "matrix_address": self.matrix_address,
            "gate_address": self.gate_address,
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
    "MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT",
    "MODULE_CERTIFICATION_PACKET_ARTIFACT_PREFIX",
    "MODULE_CERTIFICATION_PACKET_BOUNDARY",
    "MODULE_CERTIFICATION_PACKET_MANIFEST",
    "MODULE_CERTIFICATION_PACKET_VERSION",
    "ModuleCertificationPacket",
    "ModuleCertificationPacketArtifact",
    "ModuleCertificationPacketArtifactKind",
    "ModuleCertificationPacketCheck",
    "ModuleCertificationPacketCheckPlane",
    "ModuleCertificationPacketState",
    "ModuleCertificationPacketVerification",
]
