"""Runtime receipts for the archive-store replication lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-runtime-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_replication_runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_STAGE_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-runtime-stage"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_MAX_STAGES = 32


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind(StrEnum):
    PLAN = "plan"
    VERIFY_SOURCE = "verify_source"
    VERIFY_TARGET = "verify_target"
    RECONCILE = "reconcile"
    APPLY = "apply"
    PROMOTE = "promote"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _address(value: Any, field: str) -> str:
    normalized = _text(value, field, 2048)
    if ":" not in normalized:
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the supported bound")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage:
    """One deterministic lifecycle stage."""

    ordinal: int
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState
    artifact_address: str
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(
            self.ordinal,
            "replication runtime stage ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_MAX_STAGES,
        )
        _address(self.artifact_address, "replication runtime artifact address")
        _address(self.content_address, "replication runtime stage address")
        if not isinstance(
            self.kind, ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind
        ):
            raise ValidationError("replication runtime stage kind is invalid")
        if not isinstance(
            self.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState
        ):
            raise ValidationError("replication runtime stage state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("replication runtime stage acceptance must be boolean")
        if self.accepted != (
            self.state
            is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED
        ):
            raise ValidationError("replication runtime stage state and acceptance disagree")
        _text(self.detail, "replication runtime stage detail", 4096)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "state": self.state,
            "artifact_address": self.artifact_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_STAGE_PREFIX,
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime:
    """Full plan/verify/apply/promote lifecycle receipt."""

    replication_id: str
    version: str
    boundary: str
    source_store_id: str
    target_store_id: str
    plan_address: str
    receipt_address: str | None
    promotion_address: str
    stages: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage, ...]
    stage_count: int
    completed_count: int
    skipped_count: int
    blocked_count: int
    apply_requested: bool
    object_copy_count: int
    operation_copy_count: int
    required_byte_count: int
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.replication_id, "runtime replication ID", 512)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_VERSION
        ):
            raise ValidationError("replication runtime version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_BOUNDARY
        ):
            raise ValidationError("replication runtime boundary is invalid")
        _text(self.source_store_id, "runtime source store ID")
        _text(self.target_store_id, "runtime target store ID")
        _address(self.plan_address, "runtime plan address")
        if self.receipt_address is not None:
            _address(self.receipt_address, "runtime receipt address")
        _address(self.promotion_address, "runtime promotion address")
        _address(self.content_address, "runtime address")
        _count(
            self.stage_count,
            "runtime stage count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_MAX_STAGES,
        )
        _count(self.completed_count, "runtime completed count")
        _count(self.skipped_count, "runtime skipped count")
        _count(self.blocked_count, "runtime blocked count")
        _count(self.object_copy_count, "runtime object copy count")
        _count(self.operation_copy_count, "runtime operation copy count")
        _count(self.required_byte_count, "runtime required byte count")
        if self.stage_count != len(self.stages):
            raise ValidationError("runtime stage count does not conserve")
        if self.completed_count != sum(
            item.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED
            for item in self.stages
        ):
            raise ValidationError("runtime completed count does not conserve")
        if self.skipped_count != sum(
            item.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.SKIPPED
            for item in self.stages
        ):
            raise ValidationError("runtime skipped count does not conserve")
        if self.blocked_count != sum(
            item.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED
            for item in self.stages
        ):
            raise ValidationError("runtime blocked count does not conserve")
        if not isinstance(self.apply_requested, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("runtime flags must be boolean")
        if self.accepted != (self.blocked_count == 0):
            raise ValidationError("runtime acceptance does not conserve")
        if tuple(item.ordinal for item in self.stages) != tuple(range(self.stage_count)):
            raise ValidationError("runtime stage ordinals must be contiguous")
        _text(self.detail, "runtime detail", 8192)

    def to_dict(self) -> dict[str, Any]:
        return {
            "replication_id": self.replication_id,
            "version": self.version,
            "boundary": self.boundary,
            "source_store_id": self.source_store_id,
            "target_store_id": self.target_store_id,
            "plan_address": self.plan_address,
            "receipt_address": self.receipt_address,
            "promotion_address": self.promotion_address,
            "stages": [item.to_dict() for item in self.stages],
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "skipped_count": self.skipped_count,
            "blocked_count": self.blocked_count,
            "apply_requested": self.apply_requested,
            "object_copy_count": self.object_copy_count,
            "operation_copy_count": self.operation_copy_count,
            "required_byte_count": self.required_byte_count,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "stages"}


def address_module_workbench_execution_packet_archive_store_replication_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_PREFIX
    )


def module_workbench_execution_packet_archive_store_replication_runtime_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_BOUNDARY,
        "stage_kinds": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind
        ],
        "stage_states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState
        ],
        "max_stages": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_MAX_STAGES
        ),
        "outputs": ["plan_address", "receipt_address", "promotion_address", "stages", "summary"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_runtime_capabilities() -> dict[
    str, Any
]:
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_VERSION,
        "operations": [
            "plan_stage",
            "verify_source_stage",
            "verify_target_stage",
            "reconcile_stage",
            "apply_stage",
            "promote_stage",
            "complete_stage",
            "skip_unrequested_apply",
            "address_each_stage",
            "address_complete_runtime",
            "query_runtime_summary",
            "query_runtime_stages",
            "export_runtime_json",
            "export_runtime_csv",
        ],
        "guarantees": [
            "stage_order_is_contiguous",
            "stage_counts_conserve",
            "blocked_stage_fails_runtime",
            "unrequested_apply_is_explicitly_skipped",
            "no_paths_in_runtime_receipt",
        ],
    }
