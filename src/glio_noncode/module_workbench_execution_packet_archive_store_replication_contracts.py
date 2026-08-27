"""Typed public contracts for archive-store replication and promotion.

Replication is deliberately modelled as a content-addressed planning boundary.
The plan can describe an offline transfer without exposing filesystem locations,
binary payloads, machine identity, or wall-clock metadata.  Applying a plan is
an explicitly separate operation that may write a complete verified store to a
caller-selected destination.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_replication"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_ENTRY_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-entry"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_OPERATION_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-operation"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RECEIPT_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-receipt"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_CHECK_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_QUERY_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS = 8192


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationState(StrEnum):
    """The result of comparing a source store with a target store."""

    MATCHED = "matched"
    EXTENDED = "extended"
    DIVERGED = "diverged"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction(StrEnum):
    """Object disposition in a replication plan."""

    REUSE = "reuse"
    COPY = "copy"
    CONFLICT = "conflict"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction(StrEnum):
    """Journal disposition in a replication plan."""

    REUSE = "reuse"
    COPY = "copy"
    CONFLICT = "conflict"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane(StrEnum):
    """Independent safety planes used when planning or applying a transfer."""

    IDENTITY = "identity"
    SOURCE = "source"
    TARGET = "target"
    ANCESTRY = "ancestry"
    OBJECT = "object"
    OPERATION = "operation"
    DESTINATION = "destination"
    PUBLIC = "public"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState(StrEnum):
    """One check's outcome."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState(StrEnum):
    """Outcome of an explicit apply operation."""

    APPLIED = "applied"
    NOOP = "noop"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStorePromotionState(StrEnum):
    """Whether a replication result can be promoted as the target boundary."""

    PROMOTABLE = "promotable"
    HOLD = "hold"
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


def _ratio(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if value < 0 or value > 1:
        raise ValidationError(f"{field} must be between zero and one")


def _enum(value: Any, enum_type: type[StrEnum], field: str) -> StrEnum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} is invalid") from exc


def _address_rows(values: tuple[str, ...], field: str) -> None:
    _count(
        len(values),
        field,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS,
    )
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    for value in values:
        _address(value, field)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry:
    """One source archive object and its target disposition."""

    ordinal: int
    archive_address: str
    object_key: str
    source_entry_address: str
    target_entry_address: str | None
    action: ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction
    byte_count: int
    required: bool
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(
            self.ordinal,
            "replication entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS,
        )
        for value, field in (
            (self.archive_address, "archive address"),
            (self.source_entry_address, "source entry address"),
            (self.content_address, "replication entry address"),
        ):
            _address(value, field)
        if self.target_entry_address is not None:
            _address(self.target_entry_address, "target entry address")
        _text(self.object_key, "object key", 512)
        if "/" in self.object_key or "\\" in self.object_key or ":" in self.object_key:
            raise ValidationError("replication object key is unsafe")
        _count(self.byte_count, "replication byte count")
        _enum(
            self.action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction,
            "entry action",
        )
        if not isinstance(self.required, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("replication entry flags must be boolean")
        _text(self.detail, "replication entry detail", 4096)
        if self.required != (
            self.action
            is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.REUSE
        ):
            raise ValidationError("replication entry required flag is inconsistent")
        if self.accepted != (
            self.action
            is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.CONFLICT
        ):
            raise ValidationError("replication entry acceptance is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "archive_address": self.archive_address,
            "object_key": self.object_key,
            "source_entry_address": self.source_entry_address,
            "target_entry_address": self.target_entry_address,
            "action": self.action,
            "byte_count": self.byte_count,
            "required": self.required,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_ENTRY_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation:
    """One source journal record and its target disposition."""

    ordinal: int
    operation_address: str
    operation_id: str
    previous_address: str
    source_result_address: str
    target_operation_address: str | None
    action: ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction
    required: bool
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(
            self.ordinal,
            "replication operation ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS,
        )
        for value, field in (
            (self.operation_address, "operation address"),
            (self.source_result_address, "source result address"),
            (self.content_address, "replication operation address"),
        ):
            _address(value, field)
        if self.previous_address != "module-workbench-execution-packet-archive-store-genesis":
            _address(self.previous_address, "previous address")
        else:
            _text(self.previous_address, "previous address")
        if self.target_operation_address is not None:
            _address(self.target_operation_address, "target operation address")
        _text(self.operation_id, "operation ID", 512)
        _enum(
            self.action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction,
            "operation action",
        )
        if not isinstance(self.required, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("replication operation flags must be boolean")
        _text(self.detail, "replication operation detail", 4096)
        if self.required != (
            self.action
            is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.REUSE
        ):
            raise ValidationError("replication operation required flag is inconsistent")
        if self.accepted != (
            self.action
            is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.CONFLICT
        ):
            raise ValidationError("replication operation acceptance is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "operation_address": self.operation_address,
            "operation_id": self.operation_id,
            "previous_address": self.previous_address,
            "source_result_address": self.source_result_address,
            "target_operation_address": self.target_operation_address,
            "action": self.action,
            "required": self.required,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_operation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_OPERATION_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck:
    """A bounded, independently inspectable replication safety check."""

    check_id: str
    plane: ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _address(self.check_id, "replication check ID")
        _address(self.content_address, "replication check address")
        _enum(
            self.plane,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane,
            "replication check plane",
        )
        _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState,
            "replication check state",
        )
        if not isinstance(self.passed, bool):
            raise ValidationError("replication check passed flag must be boolean")
        if self.passed != (
            self.state is ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckState.PASSED
        ):
            raise ValidationError("replication check state and passed flag disagree")
        _text(self.detail, "replication check detail", 4096)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "plane": self.plane,
            "state": self.state,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_CHECK_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan:
    """Immutable transfer plan for an append-only archive-store lineage."""

    replication_id: str
    version: str
    boundary: str
    source_store_id: str
    target_store_id: str
    source_store_address: str
    target_store_address: str
    source_head_address: str
    target_head_address: str
    source_archive_count: int
    target_archive_count: int
    source_operation_count: int
    target_operation_count: int
    source_byte_count: int
    target_byte_count: int
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationState
    entries: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntry, ...]
    operations: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperation, ...]
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck, ...]
    object_count: int
    object_copy_count: int
    object_reuse_count: int
    object_conflict_count: int
    operation_count: int
    operation_copy_count: int
    operation_reuse_count: int
    operation_conflict_count: int
    required_byte_count: int
    transfer_ratio: float
    apply_allowed: bool
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.replication_id, "replication ID", 512)
        if self.version != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_VERSION:
            raise ValidationError("replication version is invalid")
        if self.boundary != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_BOUNDARY:
            raise ValidationError("replication boundary is invalid")
        for value, field in (
            (self.source_store_address, "source store address"),
            (self.target_store_address, "target store address"),
            (self.source_head_address, "source head address"),
            (self.target_head_address, "target head address"),
            (self.content_address, "replication plan address"),
        ):
            _address(value, field)
        _text(self.source_store_id, "source store ID")
        _text(self.target_store_id, "target store ID")
        for value, field in (
            (self.source_archive_count, "source archive count"),
            (self.target_archive_count, "target archive count"),
            (self.source_operation_count, "source operation count"),
            (self.target_operation_count, "target operation count"),
            (self.source_byte_count, "source byte count"),
            (self.target_byte_count, "target byte count"),
        ):
            _count(value, field)
        for value, field in (
            (self.object_count, "replication object count"),
            (self.object_copy_count, "replication object copy count"),
            (self.object_reuse_count, "replication object reuse count"),
            (self.object_conflict_count, "replication object conflict count"),
            (self.operation_count, "replication operation count"),
            (self.operation_copy_count, "replication operation copy count"),
            (self.operation_reuse_count, "replication operation reuse count"),
            (self.operation_conflict_count, "replication operation conflict count"),
        ):
            _count(
                value, field, MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS
            )
        _count(self.required_byte_count, "replication required byte count")
        _ratio(self.transfer_ratio, "replication transfer ratio")
        _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationState,
            "replication state",
        )
        _count(
            len(self.entries),
            "replication entries",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS,
        )
        _count(
            len(self.operations),
            "replication operations",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS,
        )
        _count(
            len(self.checks),
            "replication checks",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_ROWS,
        )
        if self.object_count != len(self.entries) or self.operation_count != len(self.operations):
            raise ValidationError("replication plan counts do not conserve")
        if (
            self.object_copy_count + self.object_reuse_count + self.object_conflict_count
            != self.object_count
        ):
            raise ValidationError("replication object actions do not conserve")
        if (
            self.operation_copy_count + self.operation_reuse_count + self.operation_conflict_count
            != self.operation_count
        ):
            raise ValidationError("replication operation actions do not conserve")
        if self.required_byte_count != sum(
            item.byte_count for item in self.entries if item.required
        ):
            raise ValidationError("replication byte requirement does not conserve")
        if self.transfer_ratio != (
            self.required_byte_count / self.source_byte_count if self.source_byte_count else 0
        ):
            raise ValidationError("replication transfer ratio does not conserve")
        if self.accepted != (
            self.state
            in {
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.MATCHED,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.EXTENDED,
            }
            and all(item.passed for item in self.checks)
            and not any(not item.accepted for item in self.entries)
            and not any(not item.accepted for item in self.operations)
        ):
            raise ValidationError("replication plan acceptance does not conserve")
        if self.apply_allowed != (
            self.accepted
            and self.state is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.MATCHED
        ):
            raise ValidationError("replication apply allowance does not conserve")
        _text(self.detail, "replication plan detail", 8192)

    def to_dict(self) -> dict[str, Any]:
        return {
            "replication_id": self.replication_id,
            "version": self.version,
            "boundary": self.boundary,
            "source_store_id": self.source_store_id,
            "target_store_id": self.target_store_id,
            "source_store_address": self.source_store_address,
            "target_store_address": self.target_store_address,
            "source_head_address": self.source_head_address,
            "target_head_address": self.target_head_address,
            "source_archive_count": self.source_archive_count,
            "target_archive_count": self.target_archive_count,
            "source_operation_count": self.source_operation_count,
            "target_operation_count": self.target_operation_count,
            "source_byte_count": self.source_byte_count,
            "target_byte_count": self.target_byte_count,
            "state": self.state,
            "entries": [item.to_dict() for item in self.entries],
            "operations": [item.to_dict() for item in self.operations],
            "checks": [item.to_dict() for item in self.checks],
            "object_count": self.object_count,
            "object_copy_count": self.object_copy_count,
            "object_reuse_count": self.object_reuse_count,
            "object_conflict_count": self.object_conflict_count,
            "operation_count": self.operation_count,
            "operation_copy_count": self.operation_copy_count,
            "operation_reuse_count": self.operation_reuse_count,
            "operation_conflict_count": self.operation_conflict_count,
            "required_byte_count": self.required_byte_count,
            "transfer_ratio": self.transfer_ratio,
            "apply_allowed": self.apply_allowed,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.to_dict().items()
            if key not in {"entries", "operations", "checks"}
        }


def address_module_workbench_execution_packet_archive_store_replication(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt:
    """Path-free proof of an applied, noop, or blocked transfer."""

    replication_id: str
    plan_address: str
    source_store_id: str
    target_store_id: str
    before_target_address: str
    after_target_address: str
    before_target_head_address: str
    after_target_head_address: str
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState
    object_copy_count: int
    object_reuse_count: int
    operation_copy_count: int
    operation_reuse_count: int
    byte_count: int
    expected_head_address: str | None
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.replication_id, "receipt replication ID", 512)
        for value, field in (
            (self.plan_address, "plan address"),
            (self.before_target_address, "before target address"),
            (self.after_target_address, "after target address"),
            (self.before_target_head_address, "before target head address"),
            (self.after_target_head_address, "after target head address"),
            (self.content_address, "receipt address"),
        ):
            _address(value, field)
        _text(self.source_store_id, "receipt source store ID")
        _text(self.target_store_id, "receipt target store ID")
        if self.expected_head_address is not None:
            _address(self.expected_head_address, "expected head address")
        _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState,
            "receipt state",
        )
        for value, field in (
            (self.object_copy_count, "receipt object copy count"),
            (self.object_reuse_count, "receipt object reuse count"),
            (self.operation_copy_count, "receipt operation copy count"),
            (self.operation_reuse_count, "receipt operation reuse count"),
            (self.byte_count, "receipt byte count"),
        ):
            _count(value, field)
        if not isinstance(self.accepted, bool):
            raise ValidationError("receipt acceptance must be boolean")
        if self.accepted != (
            self.state
            in {
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState.APPLIED,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState.NOOP,
            }
        ):
            raise ValidationError("receipt state and acceptance disagree")
        _text(self.detail, "receipt detail", 8192)

    def to_dict(self) -> dict[str, Any]:
        return {
            "replication_id": self.replication_id,
            "plan_address": self.plan_address,
            "source_store_id": self.source_store_id,
            "target_store_id": self.target_store_id,
            "before_target_address": self.before_target_address,
            "after_target_address": self.after_target_address,
            "before_target_head_address": self.before_target_head_address,
            "after_target_head_address": self.after_target_head_address,
            "state": self.state,
            "object_copy_count": self.object_copy_count,
            "object_reuse_count": self.object_reuse_count,
            "operation_copy_count": self.operation_copy_count,
            "operation_reuse_count": self.operation_reuse_count,
            "byte_count": self.byte_count,
            "expected_head_address": self.expected_head_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_receipt(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RECEIPT_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStorePromotion:
    """A reviewable promotion decision for a verified replication boundary."""

    promotion_id: str
    plan_address: str
    receipt_address: str | None
    source_store_id: str
    target_store_id: str
    source_store_address: str
    target_store_address: str
    state: ModuleWorkbenchExecutionPacketArchiveStorePromotionState
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheck, ...]
    required_check_count: int
    passed_check_count: int
    release_allowed: bool
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.promotion_id, "promotion ID", 512)
        for value, field in (
            (self.plan_address, "promotion plan address"),
            (self.source_store_address, "promotion source store address"),
            (self.target_store_address, "promotion target store address"),
            (self.content_address, "promotion address"),
        ):
            _address(value, field)
        _text(self.source_store_id, "promotion source store ID")
        _text(self.target_store_id, "promotion target store ID")
        if self.receipt_address is not None:
            _address(self.receipt_address, "promotion receipt address")
        _enum(
            self.state, ModuleWorkbenchExecutionPacketArchiveStorePromotionState, "promotion state"
        )
        _count(self.required_check_count, "promotion required check count")
        _count(self.passed_check_count, "promotion passed check count")
        if self.required_check_count != len(self.checks):
            raise ValidationError("promotion check count does not conserve")
        if self.passed_check_count != sum(item.passed for item in self.checks):
            raise ValidationError("promotion passed count does not conserve")
        if not isinstance(self.release_allowed, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("promotion flags must be boolean")
        if self.release_allowed != (
            self.state is ModuleWorkbenchExecutionPacketArchiveStorePromotionState.PROMOTABLE
        ):
            raise ValidationError("promotion release allowance is inconsistent")
        if self.accepted != self.release_allowed:
            raise ValidationError("promotion acceptance is inconsistent")
        _text(self.detail, "promotion detail", 8192)

    def to_dict(self) -> dict[str, Any]:
        return {
            "promotion_id": self.promotion_id,
            "plan_address": self.plan_address,
            "receipt_address": self.receipt_address,
            "source_store_id": self.source_store_id,
            "target_store_id": self.target_store_id,
            "source_store_address": self.source_store_address,
            "target_store_address": self.target_store_address,
            "state": self.state,
            "checks": [item.to_dict() for item in self.checks],
            "required_check_count": self.required_check_count,
            "passed_check_count": self.passed_check_count,
            "release_allowed": self.release_allowed,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}


def address_module_workbench_execution_packet_archive_store_promotion(
    value: ModuleWorkbenchExecutionPacketArchiveStorePromotion,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PREFIX
    )


def module_workbench_execution_packet_archive_store_replication_schema() -> dict[str, Any]:
    """Describe the path-free replication boundary."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_BOUNDARY,
        "resources": ["summary", "entries", "operations", "checks", "promotion"],
        "states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationState
        ],
        "entry_actions": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction
        ],
        "operation_actions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction
        ],
        "receipt_states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState
        ],
        "promotion_states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStorePromotionState
        ],
        "check_planes": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationCheckPlane
        ],
        "inputs": [
            "typed_source_store",
            "typed_target_store",
            "source_directory",
            "target_directory",
        ],
        "outputs": ["replication_plan", "apply_receipt", "promotion_decision", "query_page"],
        "guards": [
            "same_store_id",
            "append_only_ancestry",
            "expected_head",
            "verified_objects",
            "public_boundary",
        ],
        "retains_binary_payloads": False,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_capabilities() -> dict[str, Any]:
    """Declare the complete replication and promotion surface."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_VERSION,
        "operations": [
            "load_verified_source_store",
            "load_verified_target_store",
            "compare_store_identity",
            "compare_operation_ancestry",
            "compare_entry_ancestry",
            "plan_object_reuse",
            "plan_object_copy",
            "plan_operation_reuse",
            "plan_operation_copy",
            "detect_object_conflict",
            "detect_operation_conflict",
            "enforce_expected_target_head",
            "build_replication_checks",
            "build_replication_plan",
            "rehydrate_replication_plan",
            "verify_replication_plan",
            "apply_replication_plan_atomically",
            "write_path_free_apply_receipt",
            "build_promotion_decision",
            "query_replication_summary",
            "query_replication_entries",
            "query_replication_operations",
            "query_replication_checks",
            "export_replication_json",
            "export_replication_csv",
            "render_replication_markdown",
            "run_replication_runtime",
        ],
        "guarantees": [
            "deterministic_content_addresses",
            "append_only_lineage_proof",
            "deduplicated_object_accounting",
            "stale_head_rejection",
            "divergence_is_fail_closed",
            "atomic_destination_replace",
            "no_binary_payloads_in_public_receipts",
            "no_filesystem_paths_in_public_receipts",
            "no_timestamps_or_identity_metadata",
        ],
    }
