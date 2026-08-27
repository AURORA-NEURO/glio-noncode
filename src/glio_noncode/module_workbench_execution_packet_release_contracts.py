"""Contracts for accepting or holding an execution packet release."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_VERSION = "module-workbench-execution-packet-release-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_release"
)
MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_MAX_CHECKS = 32


class ModuleWorkbenchExecutionPacketReleaseState(StrEnum):
    """Lifecycle state for a packet release decision."""

    DRAFT = "draft"
    READY = "ready"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class ModuleWorkbenchExecutionPacketReleasePlane(StrEnum):
    """Independent release decision planes."""

    PACKET = "packet"
    VERIFICATION = "verification"
    REPLAY = "replay"
    THRESHOLD = "threshold"
    PUBLIC = "public"


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


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketReleaseCheck:
    """One release gate result with observed and required values."""

    check_id: str
    plane: ModuleWorkbenchExecutionPacketReleasePlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchExecutionPacketReleasePlane):
            raise ValidationError("release plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("release check result must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_packet_release_check(
    value: ModuleWorkbenchExecutionPacketReleaseCheck,
) -> str:
    """Address one release check."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-release-check")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketRelease:
    """Addressed release decision for a portable execution packet."""

    release_id: str
    packet_id: str
    packet_address: str
    verification_address: str
    replay_address: str
    minimum_artifact_count: int
    minimum_passed_check_count: int
    state: ModuleWorkbenchExecutionPacketReleaseState
    accepted: bool
    checks: tuple[ModuleWorkbenchExecutionPacketReleaseCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "release_id",
            "packet_id",
            "packet_address",
            "verification_address",
            "replay_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        _count(self.minimum_artifact_count, "minimum_artifact_count")
        _count(self.minimum_passed_check_count, "minimum_passed_check_count")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketReleaseState):
            raise ValidationError("release state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("release accepted flag must be boolean")
        if (
            not self.checks
            or len(self.checks) > MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_MAX_CHECKS
        ):
            raise ValidationError("release checks are incomplete or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("release checks must be sorted and unique")

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_BOUNDARY,
            "release_id": self.release_id,
            "packet_id": self.packet_id,
            "packet_address": self.packet_address,
            "verification_address": self.verification_address,
            "replay_address": self.replay_address,
            "minimum_artifact_count": self.minimum_artifact_count,
            "minimum_passed_check_count": self.minimum_passed_check_count,
            "state": self.state,
            "accepted": self.accepted,
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "content_address": self.content_address,
        }
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_packet_release(
    value: ModuleWorkbenchExecutionPacketRelease,
) -> str:
    """Address a release decision without relying on filesystem paths."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-release")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_MAX_CHECKS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_RELEASE_VERSION",
    "ModuleWorkbenchExecutionPacketRelease",
    "ModuleWorkbenchExecutionPacketReleaseCheck",
    "ModuleWorkbenchExecutionPacketReleasePlane",
    "ModuleWorkbenchExecutionPacketReleaseState",
    "address_module_workbench_execution_packet_release",
    "address_module_workbench_execution_packet_release_check",
]
