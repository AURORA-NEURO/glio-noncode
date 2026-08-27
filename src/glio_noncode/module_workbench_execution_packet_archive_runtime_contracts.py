"""Contracts for the ordered packet archive transport runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_VERSION = (
    "module-workbench-execution-packet-archive-runtime-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_MAX_STAGES = 9


class ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind(StrEnum):
    """Ordered lifecycle stages for an archive handoff."""

    BUILD = "build"
    WRITE = "write"
    VERIFY = "verify"
    LOAD = "load"
    CHUNK = "chunk"
    RESUME = "resume"
    ASSEMBLE = "assemble"
    UNPACK = "unpack"
    QUERY = "query"


class ModuleWorkbenchExecutionPacketArchiveRuntimeStageState(StrEnum):
    """Terminal state for one archive runtime stage."""

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
class ModuleWorkbenchExecutionPacketArchiveRuntimeStage:
    """One addressed archive transport stage."""

    kind: ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind
    state: ModuleWorkbenchExecutionPacketArchiveRuntimeStageState
    accepted: bool
    artifact_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind):
            raise ValidationError("archive runtime stage kind is invalid")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketArchiveRuntimeStageState):
            raise ValidationError("archive runtime stage state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("archive runtime stage acceptance must be boolean")
        _text(self.artifact_address, "artifact_address", 512)
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address", 512)
        if self.accepted != (
            self.state is ModuleWorkbenchExecutionPacketArchiveRuntimeStageState.COMPLETED
        ):
            raise ValidationError("archive runtime stage state and acceptance do not agree")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_packet_archive_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveRuntimeStage,
) -> str:
    """Address one runtime stage."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-archive-runtime-stage")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveRuntime:
    """Whole ordered archive transport runtime."""

    archive_id: str
    archive_address: str
    verification_address: str
    transfer_address: str
    reassembled_address: str
    stages: tuple[ModuleWorkbenchExecutionPacketArchiveRuntimeStage, ...]
    stage_count: int
    completed_count: int
    blocked_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "archive_id",
            "archive_address",
            "verification_address",
            "transfer_address",
            "reassembled_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        if (
            not self.stages
            or len(self.stages) > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_MAX_STAGES
        ):
            raise ValidationError("archive runtime stages are incomplete or excessive")
        expected = tuple(ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind)
        if tuple(item.kind for item in self.stages) != expected:
            raise ValidationError("archive runtime stage order is invalid")
        _count(self.stage_count, "stage_count")
        _count(self.completed_count, "completed_count")
        _count(self.blocked_count, "blocked_count")
        if self.stage_count != len(self.stages):
            raise ValidationError("archive runtime stage count does not conserve")
        if self.completed_count + self.blocked_count != self.stage_count:
            raise ValidationError("archive runtime state counts do not conserve")
        if self.completed_count != sum(item.accepted for item in self.stages):
            raise ValidationError("archive runtime completed count is inconsistent")
        if not isinstance(self.accepted, bool) or self.accepted != all(
            item.accepted for item in self.stages
        ):
            raise ValidationError("archive runtime acceptance is inconsistent")

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_BOUNDARY,
            "archive_id": self.archive_id,
            "archive_address": self.archive_address,
            "verification_address": self.verification_address,
            "transfer_address": self.transfer_address,
            "reassembled_address": self.reassembled_address,
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def address_module_workbench_execution_packet_archive_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveRuntime,
) -> str:
    """Address the complete archive runtime."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-archive-runtime")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_MAX_STAGES",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_VERSION",
    "ModuleWorkbenchExecutionPacketArchiveRuntime",
    "ModuleWorkbenchExecutionPacketArchiveRuntimeStage",
    "ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind",
    "ModuleWorkbenchExecutionPacketArchiveRuntimeStageState",
    "address_module_workbench_execution_packet_archive_runtime",
    "address_module_workbench_execution_packet_archive_runtime_stage",
]
