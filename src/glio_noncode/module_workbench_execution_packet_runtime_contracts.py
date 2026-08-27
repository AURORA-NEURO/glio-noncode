"""Contracts for the ordered packet build-to-release runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_VERSION = "module-workbench-execution-packet-runtime-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_MAX_LIMIT = 512


class ModuleWorkbenchExecutionPacketRuntimeStageKind(StrEnum):
    """Ordered stages in a portable packet handoff."""

    BUILD = "build"
    WRITE = "write"
    VERIFY = "verify"
    LOAD = "load"
    QUERY = "query"
    REPLAY = "replay"
    RELEASE = "release"


class ModuleWorkbenchExecutionPacketRuntimeStageState(StrEnum):
    """Terminal state of one runtime stage."""

    COMPLETED = "completed"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketRuntimeStage:
    """One addressed build, storage, verification, or release stage."""

    kind: ModuleWorkbenchExecutionPacketRuntimeStageKind
    state: ModuleWorkbenchExecutionPacketRuntimeStageState
    accepted: bool
    artifact_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ModuleWorkbenchExecutionPacketRuntimeStageKind):
            raise ValidationError("runtime stage kind is invalid")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketRuntimeStageState):
            raise ValidationError("runtime stage state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("runtime stage acceptance must be boolean")
        _text(self.artifact_address, "artifact_address", 512)
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address", 512)
        if (
            self.accepted
            and self.state is not ModuleWorkbenchExecutionPacketRuntimeStageState.COMPLETED
        ):
            raise ValidationError("accepted stage must be completed")
        if (
            not self.accepted
            and self.state is not ModuleWorkbenchExecutionPacketRuntimeStageState.BLOCKED
        ):
            raise ValidationError("blocked stage must not be accepted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_packet_runtime_stage(
    value: ModuleWorkbenchExecutionPacketRuntimeStage,
) -> str:
    """Address one runtime stage."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-runtime-stage")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketRuntime:
    """Whole ordered packet runtime with retained artifact addresses."""

    packet_id: str
    packet_address: str
    verification_address: str
    replay_address: str
    release_address: str
    stages: tuple[ModuleWorkbenchExecutionPacketRuntimeStage, ...]
    stage_count: int
    completed_count: int
    blocked_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "packet_id",
            "packet_address",
            "verification_address",
            "replay_address",
            "release_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        if not self.stages:
            raise ValidationError("packet runtime requires stages")
        kinds = tuple(item.kind for item in self.stages)
        expected = tuple(ModuleWorkbenchExecutionPacketRuntimeStageKind)
        if kinds != expected:
            raise ValidationError("packet runtime stages must follow the declared order")
        _count(self.stage_count, "stage_count")
        _count(self.completed_count, "completed_count")
        _count(self.blocked_count, "blocked_count")
        if self.stage_count != len(self.stages):
            raise ValidationError("packet runtime stage count does not conserve rows")
        if self.completed_count + self.blocked_count != self.stage_count:
            raise ValidationError("packet runtime stage states do not conserve rows")
        if self.completed_count != sum(item.accepted for item in self.stages):
            raise ValidationError("packet runtime completed count is inconsistent")
        if not isinstance(self.accepted, bool):
            raise ValidationError("packet runtime acceptance must be boolean")
        if self.accepted != all(item.accepted for item in self.stages):
            raise ValidationError("packet runtime acceptance does not conserve stages")

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_BOUNDARY,
            "packet_id": self.packet_id,
            "packet_address": self.packet_address,
            "verification_address": self.verification_address,
            "replay_address": self.replay_address,
            "release_address": self.release_address,
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def address_module_workbench_execution_packet_runtime(
    value: ModuleWorkbenchExecutionPacketRuntime,
) -> str:
    """Address the ordered runtime."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-runtime")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_RUNTIME_VERSION",
    "ModuleWorkbenchExecutionPacketRuntime",
    "ModuleWorkbenchExecutionPacketRuntimeStage",
    "ModuleWorkbenchExecutionPacketRuntimeStageKind",
    "ModuleWorkbenchExecutionPacketRuntimeStageState",
    "address_module_workbench_execution_packet_runtime",
    "address_module_workbench_execution_packet_runtime_stage",
]
