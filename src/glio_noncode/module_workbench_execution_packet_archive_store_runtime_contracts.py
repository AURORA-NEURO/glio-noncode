"""Contracts for the ordered archive store lifecycle runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_VERSION = (
    "module-workbench-execution-packet-archive-store-runtime-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_MAX_STAGES = 8
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_STAGE_PREFIX = (
    "module-workbench-execution-packet-archive-store-runtime-stage"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_PREFIX = (
    "module-workbench-execution-packet-archive-store-runtime"
)


class ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind(StrEnum):
    """Ordered store lifecycle stages."""

    BUILD = "build"
    DEDUPLICATE = "deduplicate"
    WRITE = "write"
    VERIFY = "verify"
    QUERY = "query"
    REPLAY = "replay"
    DIFF = "diff"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageState(StrEnum):
    """Stage outcome."""

    COMPLETED = "completed"
    BLOCKED = "blocked"


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value


def _count(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage:
    """One addressed stage in the store runtime."""

    ordinal: int
    kind: ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind
    state: ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageState
    accepted: bool
    artifact_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(self.ordinal, "stage ordinal")
        if not isinstance(self.kind, ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind):
            raise ValidationError("runtime stage kind is invalid")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageState):
            raise ValidationError("runtime stage state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("runtime stage acceptance must be boolean")
        _text(self.artifact_address, "stage artifact address")
        _text(self.detail, "stage detail")
        _text(self.content_address, "stage content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_address": self.artifact_address,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage,
) -> str:
    """Address one lifecycle stage."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_STAGE_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreRuntime:
    """Complete ordered store lifecycle receipt."""

    store_id: str
    store_address: str
    verification_address: str
    replay_address: str
    stages: tuple[ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage, ...]
    stage_count: int
    completed_count: int
    blocked_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "store_id",
            "store_address",
            "verification_address",
            "replay_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        expected = tuple(ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind)
        if tuple(item.kind for item in self.stages) != expected:
            raise ValidationError("store runtime stage order is invalid")
        if len(self.stages) != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_MAX_STAGES:
            raise ValidationError("store runtime must contain every stage")
        for field in ("stage_count", "completed_count", "blocked_count"):
            _count(getattr(self, field), field)
        if self.stage_count != len(self.stages):
            raise ValidationError("store runtime stage count does not conserve")
        if self.completed_count + self.blocked_count != self.stage_count:
            raise ValidationError("store runtime state counts do not conserve")
        if self.completed_count != sum(item.accepted for item in self.stages):
            raise ValidationError("store runtime completed count is inconsistent")
        if not isinstance(self.accepted, bool) or self.accepted != all(
            item.accepted for item in self.stages
        ):
            raise ValidationError("store runtime acceptance is inconsistent")

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_BOUNDARY,
            "store_id": self.store_id,
            "store_address": self.store_address,
            "verification_address": self.verification_address,
            "replay_address": self.replay_address,
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def address_module_workbench_execution_packet_archive_store_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRuntime,
) -> str:
    """Address the complete store runtime."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_PREFIX)


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_MAX_STAGES",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_STAGE_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_VERSION",
    "ModuleWorkbenchExecutionPacketArchiveStoreRuntime",
    "ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage",
    "ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind",
    "ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageState",
    "address_module_workbench_execution_packet_archive_store_runtime",
    "address_module_workbench_execution_packet_archive_store_runtime_stage",
]
