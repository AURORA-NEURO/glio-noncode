"""Typed contracts for portable module execution handoff packets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, hash_bytes, jsonable

MODULE_WORKBENCH_EXECUTION_PACKET_VERSION = "module-workbench-execution-packet-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY = "public_aggregate_module_workbench_execution_packet"
MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX = "module-workbench-execution-packet-artifact"
MODULE_WORKBENCH_EXECUTION_PACKET_CHECK_PREFIX = "module-workbench-execution-packet-check"
MODULE_WORKBENCH_EXECUTION_PACKET_VERIFICATION_PREFIX = (
    "module-workbench-execution-packet-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS = 32
MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT = 13
MODULE_WORKBENCH_EXECUTION_PACKET_MAX_CHECKS = 64


class ModuleWorkbenchExecutionPacketState(StrEnum):
    """Publication state for one portable packet."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArtifactKind(StrEnum):
    """Stable classification for every packet artifact."""

    WORKBENCH_SUMMARY = "workbench_summary"
    PORTFOLIO = "portfolio"
    INITIAL_LEDGER = "initial_ledger"
    LEDGER = "ledger"
    ITEMS = "items"
    EVENTS = "events"
    BLOCKERS = "blockers"
    REVIEW = "review"
    AUDIT = "audit"
    POLICY = "policy"
    RUNTIME = "runtime"
    SCHEMA = "schema"
    CAPABILITIES = "capabilities"


class ModuleWorkbenchExecutionPacketCheckPlane(StrEnum):
    """Independent verification plane for a packet check."""

    MANIFEST = "manifest"
    PATH = "path"
    BYTES = "bytes"
    LINKAGE = "linkage"
    SEMANTIC = "semantic"
    PUBLIC = "public"
    REPLAY = "replay"
    STORAGE = "storage"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")


def _safe_path(value: str) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
        or value.startswith("/")
    ):
        return False
    parts = tuple(value.split("/"))
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _ordered_unique(values: tuple[str, ...], field: str, maximum: int = 64) -> None:
    _count(len(values), field, maximum)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if len(set(values)) != len(values) or tuple(sorted(values)) != values:
        raise ValidationError(f"{field} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArtifact:
    """One UTF-8 packet file addressed by its exact bytes."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: ModuleWorkbenchExecutionPacketArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        _text(self.artifact_id, "artifact_id", 256)
        _text(self.relative_path, "relative_path", 512)
        _text(self.media_type, "media_type", 256)
        _text(self.content_address, "content_address", 512)
        if not isinstance(self.kind, ModuleWorkbenchExecutionPacketArtifactKind):
            raise ValidationError("artifact kind is invalid")
        if not _safe_path(self.relative_path):
            raise ValidationError("artifact path is unsafe")
        _count(self.byte_count, "byte_count")
        _count(self.line_count, "line_count")
        if self.payload is not None and not isinstance(self.payload, str):
            raise ValidationError("artifact payload must be text")
        if self.payload is not None and len(self.payload.encode("utf-8")) != self.byte_count:
            raise ValidationError("artifact byte count does not match payload")

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result = jsonable(self)
        if not include_payload:
            result.pop("payload", None)
        return result


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketCheck:
    """One inspectable packet verification result."""

    check_id: str
    plane: ModuleWorkbenchExecutionPacketCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchExecutionPacketCheckPlane):
            raise ValidationError("check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("check passed flag must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketVerification:
    """Filesystem verification receipt that survives a blocked result."""

    packet_id: str
    artifact_count: int
    present_count: int
    missing_count: int
    checks: tuple[ModuleWorkbenchExecutionPacketCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "packet_id", 512)
        _count(
            self.artifact_count, "artifact_count", MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS
        )
        _count(self.present_count, "present_count", MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS)
        _count(self.missing_count, "missing_count", MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS)
        if self.present_count + self.missing_count != self.artifact_count:
            raise ValidationError("verification artifact counts do not conserve")
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_EXECUTION_PACKET_MAX_CHECKS:
            raise ValidationError("verification checks are incomplete or excessive")
        if not isinstance(self.accepted, bool):
            raise ValidationError("verification accepted flag must be boolean")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "artifact_count": self.artifact_count,
            "present_count": self.present_count,
            "missing_count": self.missing_count,
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacket:
    """Portable execution handoff with exact-byte artifacts and checks."""

    packet_id: str
    version: str
    boundary: str
    report_address: str
    portfolio_address: str
    initial_ledger_address: str
    ledger_address: str
    review_address: str
    audit_address: str
    policy_address: str
    gate_address: str
    runtime_address: str
    state: ModuleWorkbenchExecutionPacketState
    accepted: bool
    artifacts: tuple[ModuleWorkbenchExecutionPacketArtifact, ...]
    checks: tuple[ModuleWorkbenchExecutionPacketCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "packet_id",
            "version",
            "report_address",
            "portfolio_address",
            "initial_ledger_address",
            "ledger_address",
            "review_address",
            "audit_address",
            "policy_address",
            "gate_address",
            "runtime_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        if self.version != MODULE_WORKBENCH_EXECUTION_PACKET_VERSION:
            raise ValidationError("packet version is invalid")
        if self.boundary != MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY:
            raise ValidationError("packet boundary is invalid")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketState):
            raise ValidationError("packet state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("packet accepted flag must be boolean")
        if self.accepted != (self.state is ModuleWorkbenchExecutionPacketState.ACCEPTED):
            raise ValidationError("packet state and acceptance do not agree")
        if (
            not self.artifacts
            or len(self.artifacts) > MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS
        ):
            raise ValidationError("packet artifact collection is invalid")
        ids = tuple(item.artifact_id for item in self.artifacts)
        paths = tuple(item.relative_path for item in self.artifacts)
        if len(set(ids)) != len(ids) or tuple(sorted(ids)) != ids:
            raise ValidationError("packet artifact IDs must be sorted and unique")
        if len(set(paths)) != len(paths) or tuple(sorted(paths)) != paths:
            raise ValidationError("packet artifact paths must be sorted and unique")
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_EXECUTION_PACKET_MAX_CHECKS:
            raise ValidationError("packet checks are incomplete or excessive")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "report_address": self.report_address,
            "portfolio_address": self.portfolio_address,
            "initial_ledger_address": self.initial_ledger_address,
            "ledger_address": self.ledger_address,
            "review_address": self.review_address,
            "audit_address": self.audit_address,
            "policy_address": self.policy_address,
            "gate_address": self.gate_address,
            "runtime_address": self.runtime_address,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_count": len(self.artifacts),
            "artifacts": [
                item.to_dict(include_payload=include_payloads) for item in self.artifacts
            ],
            "checks": [item.to_dict() for item in self.checks],
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_artifact(
    value: ModuleWorkbenchExecutionPacketArtifact,
) -> str:
    """Return the exact-byte address for one hydrated artifact."""

    if value.payload is None:
        raise ValidationError("artifact byte address requires a payload")
    return hash_bytes(
        value.payload.encode("utf-8"),
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
    )


def address_module_workbench_execution_packet_check(
    value: ModuleWorkbenchExecutionPacketCheck,
) -> str:
    """Address one packet check."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_CHECK_PREFIX)


def address_module_workbench_execution_packet_verification(
    value: ModuleWorkbenchExecutionPacketVerification,
) -> str:
    """Address one verification receipt."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_VERIFICATION_PREFIX)


def address_module_workbench_execution_packet(
    value: ModuleWorkbenchExecutionPacket,
) -> str:
    """Address a packet manifest without payload bytes."""

    body = value.to_dict(include_payloads=False)
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-execution-packet")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_CHECK_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST",
    "MODULE_WORKBENCH_EXECUTION_PACKET_MAX_ARTIFACTS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_MAX_CHECKS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_VERSION",
    "ModuleWorkbenchExecutionPacket",
    "ModuleWorkbenchExecutionPacketArtifact",
    "ModuleWorkbenchExecutionPacketArtifactKind",
    "ModuleWorkbenchExecutionPacketCheck",
    "ModuleWorkbenchExecutionPacketCheckPlane",
    "ModuleWorkbenchExecutionPacketState",
    "ModuleWorkbenchExecutionPacketVerification",
    "address_module_workbench_execution_packet",
    "address_module_workbench_execution_packet_artifact",
    "address_module_workbench_execution_packet_check",
    "address_module_workbench_execution_packet_verification",
]
