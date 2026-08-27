"""Typed contracts for durable execution packet archive stores."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION = (
    "module-workbench-execution-packet-archive-store-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_FORMAT = "directory-objects-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECTS_DIRECTORY = "objects"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECT_PREFIX = (
    "module-workbench-execution-packet-archive-store-object"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS = (
    "module-workbench-execution-packet-archive-store-genesis"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_PREFIX = (
    "module-workbench-execution-packet-archive-store"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_ENTRY_PREFIX = (
    "module-workbench-execution-packet-archive-store-entry"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OPERATION_PREFIX = (
    "module-workbench-execution-packet-archive-store-operation"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECK_PREFIX = (
    "module-workbench-execution-packet-archive-store-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERIFICATION_PREFIX = (
    "module-workbench-execution-packet-archive-store-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLAY_PREFIX = (
    "module-workbench-execution-packet-archive-store-replay"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_ENTRIES = 4096
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS = 8192
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_CHECKS = 256


class ModuleWorkbenchExecutionPacketArchiveStoreState(StrEnum):
    """Publication state of a durable archive store."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreEntryState(StrEnum):
    """State of an archive object in the store catalog."""

    STORED = "stored"


class ModuleWorkbenchExecutionPacketArchiveStoreOperationKind(StrEnum):
    """Append-only operation classifications."""

    REGISTER = "register"
    DEDUPLICATE = "deduplicate"


class ModuleWorkbenchExecutionPacketArchiveStoreOperationState(StrEnum):
    """Outcome state for one catalog operation."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane(StrEnum):
    """Independent store verification planes."""

    MANIFEST = "manifest"
    OBJECT = "object"
    ADDRESS = "address"
    INDEX = "index"
    STORAGE = "storage"
    PUBLIC = "public"


class ModuleWorkbenchExecutionPacketArchiveStoreReplayState(StrEnum):
    """Replay receipt state."""

    MATCHED = "matched"
    MISMATCHED = "mismatched"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 512) -> str:
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


def _address(value: Any, field: str) -> str:
    return _text(value, field, 1024)


def _object_key(value: Any) -> str:
    normalized = _text(value, "object_key", 512)
    if (
        "/" in normalized
        or "\\" in normalized
        or ":" in normalized
        or normalized in {".", ".."}
        or not normalized.endswith(".zip")
    ):
        raise ValidationError("object key is not a safe archive object token")
    return normalized


def _enum(value: Any, enum_type: type[StrEnum], field: str) -> StrEnum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} is invalid") from exc


def _sorted_unique(values: tuple[str, ...], field: str, maximum: int) -> None:
    _count(len(values), field, maximum)
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreEntry:
    """Manifest record for one unique archive object."""

    ordinal: int
    archive_id: str
    packet_id: str
    archive_address: str
    packet_address: str
    object_key: str
    byte_count: int
    state: ModuleWorkbenchExecutionPacketArchiveStoreEntryState
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _count(
            self.ordinal,
            "entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_ENTRIES,
        )
        for field in (
            "archive_id",
            "packet_id",
            "archive_address",
            "packet_address",
            "content_address",
        ):
            _address(getattr(self, field), field)
        _object_key(self.object_key)
        _count(self.byte_count, "entry byte count")
        _enum(self.state, ModuleWorkbenchExecutionPacketArchiveStoreEntryState, "entry state")
        if not isinstance(self.accepted, bool):
            raise ValidationError("entry acceptance must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "archive_id": self.archive_id,
            "packet_id": self.packet_id,
            "archive_address": self.archive_address,
            "packet_address": self.packet_address,
            "object_key": self.object_key,
            "byte_count": self.byte_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreEntry,
) -> str:
    """Address one archive store entry without binary payloads."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_ENTRY_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreOperation:
    """One immutable operation in the store's hash-linked journal."""

    ordinal: int
    operation_id: str
    kind: ModuleWorkbenchExecutionPacketArchiveStoreOperationKind
    state: ModuleWorkbenchExecutionPacketArchiveStoreOperationState
    archive_address: str
    object_key: str
    previous_address: str
    result_address: str
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(
            self.ordinal,
            "operation ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS,
        )
        for field in (
            "operation_id",
            "archive_address",
            "previous_address",
            "result_address",
            "content_address",
        ):
            _address(getattr(self, field), field)
        _object_key(self.object_key)
        _enum(self.kind, ModuleWorkbenchExecutionPacketArchiveStoreOperationKind, "operation kind")
        _enum(
            self.state, ModuleWorkbenchExecutionPacketArchiveStoreOperationState, "operation state"
        )
        if not isinstance(self.accepted, bool):
            raise ValidationError("operation acceptance must be boolean")
        _text(self.detail, "operation detail", 4096)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "operation_id": self.operation_id,
            "kind": self.kind,
            "state": self.state,
            "archive_address": self.archive_address,
            "object_key": self.object_key,
            "previous_address": self.previous_address,
            "result_address": self.result_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_operation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreOperation,
) -> str:
    """Address an operation and its predecessor link."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OPERATION_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreCheck:
    """One independent store verification check."""

    check_id: str
    plane: ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _address(self.check_id, "check ID")
        _enum(self.plane, ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane, "check plane")
        if not isinstance(self.passed, bool):
            raise ValidationError("check result must be boolean")
        _text(self.detail, "check detail", 4096)
        _address(self.content_address, "check content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "plane": self.plane,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreCheck,
) -> str:
    """Address a store check."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECK_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreVerification:
    """Addressed receipt from filesystem or typed-store verification."""

    store_id: str
    store_address: str
    head_address: str
    entry_count: int
    object_count: int
    operation_count: int
    check_count: int
    passed_count: int
    failed_count: int
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _address(self.store_id, "store ID")
        _address(self.store_address, "store address")
        _address(self.head_address, "head address")
        for field in (
            "entry_count",
            "object_count",
            "operation_count",
            "check_count",
            "passed_count",
            "failed_count",
        ):
            _count(getattr(self, field), field)
        if self.check_count != len(self.checks):
            raise ValidationError("verification check count does not conserve")
        if self.passed_count != sum(item.passed for item in self.checks):
            raise ValidationError("verification passed count does not conserve")
        if self.failed_count != self.check_count - self.passed_count:
            raise ValidationError("verification failed count does not conserve")
        if not isinstance(self.accepted, bool):
            raise ValidationError("verification acceptance must be boolean")
        _address(self.content_address, "verification content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "store_id": self.store_id,
            "store_address": self.store_address,
            "head_address": self.head_address,
            "entry_count": self.entry_count,
            "object_count": self.object_count,
            "operation_count": self.operation_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreVerification,
) -> str:
    """Address a verification receipt."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERIFICATION_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplay:
    """Comparison receipt for replaying a store from stored archive objects."""

    store_id: str
    store_address: str
    replayed_store_address: str
    entry_count: int
    operation_count: int
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplayState
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "store_id",
            "store_address",
            "replayed_store_address",
            "content_address",
        ):
            _address(getattr(self, field), field)
        _count(self.entry_count, "replay entry count")
        _count(self.operation_count, "replay operation count")
        _enum(self.state, ModuleWorkbenchExecutionPacketArchiveStoreReplayState, "replay state")
        if not isinstance(self.accepted, bool):
            raise ValidationError("replay acceptance must be boolean")
        _text(self.detail, "replay detail", 4096)

    def to_dict(self) -> dict[str, Any]:
        return {
            "store_id": self.store_id,
            "store_address": self.store_address,
            "replayed_store_address": self.replayed_store_address,
            "entry_count": self.entry_count,
            "operation_count": self.operation_count,
            "state": self.state,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replay(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplay,
) -> str:
    """Address a replay receipt."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLAY_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStore:
    """Immutable archive catalog with hidden exact-byte object payloads."""

    store_id: str
    version: str
    boundary: str
    storage_format: str
    entries: tuple[ModuleWorkbenchExecutionPacketArchiveStoreEntry, ...]
    operations: tuple[ModuleWorkbenchExecutionPacketArchiveStoreOperation, ...]
    head_address: str
    archive_count: int
    object_count: int
    operation_count: int
    total_byte_count: int
    unique_packet_count: int
    duplicate_registration_count: int
    state: ModuleWorkbenchExecutionPacketArchiveStoreState
    accepted: bool
    content_address: str
    object_payloads: tuple[bytes, ...]

    def __post_init__(self) -> None:
        _address(self.store_id, "store ID")
        _text(self.version, "store version")
        _text(self.boundary, "store boundary")
        _text(self.storage_format, "store format")
        if self.version != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION:
            raise ValidationError("store version is invalid")
        if self.boundary != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_BOUNDARY:
            raise ValidationError("store boundary is invalid")
        if self.storage_format != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_FORMAT:
            raise ValidationError("store format is invalid")
        _address(self.head_address, "head address")
        for field in (
            "archive_count",
            "object_count",
            "operation_count",
            "total_byte_count",
            "unique_packet_count",
            "duplicate_registration_count",
        ):
            _count(getattr(self, field), field)
        if not self.entries or len(self.entries) != self.archive_count:
            raise ValidationError("store entries do not conserve")
        if (
            self.object_count != len(self.object_payloads)
            or self.object_count != self.archive_count
        ):
            raise ValidationError("store object payloads do not conserve")
        if self.operation_count != len(self.operations):
            raise ValidationError("store operations do not conserve")
        if self.archive_count > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_ENTRIES:
            raise ValidationError("store entries exceed supported bound")
        if self.operation_count > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS:
            raise ValidationError("store operations exceed supported bound")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.archive_count)):
            raise ValidationError("store entry ordinals must be contiguous")
        if tuple(item.ordinal for item in self.operations) != tuple(range(self.operation_count)):
            raise ValidationError("store operation ordinals must be contiguous")
        _sorted_unique(
            tuple(item.archive_address for item in self.entries),
            "store archive addresses",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_ENTRIES,
        )
        _sorted_unique(
            tuple(item.object_key for item in self.entries),
            "store object keys",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_ENTRIES,
        )
        _sorted_unique(
            tuple(item.operation_id for item in self.operations),
            "store operation IDs",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS,
        )
        _sorted_unique(
            tuple(item.content_address for item in self.operations),
            "store operation addresses",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS,
        )
        if self.total_byte_count != sum(len(item) for item in self.object_payloads):
            raise ValidationError("store byte count does not conserve")
        if any(not isinstance(item, bytes) or not item for item in self.object_payloads):
            raise ValidationError("store object payloads must be non-empty bytes")
        if any(
            item.byte_count != len(payload)
            for item, payload in zip(self.entries, self.object_payloads, strict=True)
        ):
            raise ValidationError("store entry byte counts do not match objects")
        if self.unique_packet_count != len({item.packet_address for item in self.entries}):
            raise ValidationError("store packet count is inconsistent")
        if self.duplicate_registration_count != sum(
            item.kind is ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.DEDUPLICATE
            for item in self.operations
        ):
            raise ValidationError("store duplicate operation count is inconsistent")
        expected_head = (
            self.operations[-1].content_address
            if self.operations
            else MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS
        )
        if self.head_address != expected_head:
            raise ValidationError("store head does not match operation journal")
        previous = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS
        for operation in self.operations:
            if operation.previous_address != previous:
                raise ValidationError("store operation chain is not contiguous")
            previous = operation.content_address
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketArchiveStoreState):
            raise ValidationError("store state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("store acceptance must be boolean")
        if self.accepted != (
            self.state is ModuleWorkbenchExecutionPacketArchiveStoreState.ACCEPTED
        ):
            raise ValidationError("store state and acceptance do not agree")
        _address(self.content_address, "store content address")

    def to_dict(
        self, *, include_entries: bool = True, include_operations: bool = True
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": self.version,
            "boundary": self.boundary,
            "storage_format": self.storage_format,
            "store_id": self.store_id,
            "head_address": self.head_address,
            "archive_count": self.archive_count,
            "object_count": self.object_count,
            "operation_count": self.operation_count,
            "total_byte_count": self.total_byte_count,
            "unique_packet_count": self.unique_packet_count,
            "duplicate_registration_count": self.duplicate_registration_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        if include_operations:
            body["operations"] = [item.to_dict() for item in self.operations]
        return body

    def summary(self) -> dict[str, Any]:
        return self.to_dict(include_entries=False, include_operations=False)


def address_module_workbench_execution_packet_archive_store(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
) -> str:
    """Address the store manifest without embedding archive bytes."""

    body = {
        key: item
        for key, item in value.to_dict(include_entries=True, include_operations=True).items()
        if key != "content_address"
    }
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_PREFIX)


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECK_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_ENTRY_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_FORMAT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MANIFEST",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_CHECKS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_ENTRIES",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECTS_DIRECTORY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OBJECT_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_OPERATION_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLAY_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERIFICATION_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION",
    "ModuleWorkbenchExecutionPacketArchiveStore",
    "ModuleWorkbenchExecutionPacketArchiveStoreCheck",
    "ModuleWorkbenchExecutionPacketArchiveStoreCheckPlane",
    "ModuleWorkbenchExecutionPacketArchiveStoreEntry",
    "ModuleWorkbenchExecutionPacketArchiveStoreEntryState",
    "ModuleWorkbenchExecutionPacketArchiveStoreOperation",
    "ModuleWorkbenchExecutionPacketArchiveStoreOperationKind",
    "ModuleWorkbenchExecutionPacketArchiveStoreOperationState",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplay",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplayState",
    "ModuleWorkbenchExecutionPacketArchiveStoreState",
    "ModuleWorkbenchExecutionPacketArchiveStoreVerification",
    "address_module_workbench_execution_packet_archive_store",
    "address_module_workbench_execution_packet_archive_store_check",
    "address_module_workbench_execution_packet_archive_store_entry",
    "address_module_workbench_execution_packet_archive_store_operation",
    "address_module_workbench_execution_packet_archive_store_replay",
    "address_module_workbench_execution_packet_archive_store_verification",
]
