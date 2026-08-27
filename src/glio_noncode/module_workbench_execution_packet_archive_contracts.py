"""Contracts for transporting exact-byte execution packets as archives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, hash_bytes, jsonable

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERSION = (
    "module-workbench-execution-packet-archive-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT = "zip-stored-utf8-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_PREFIX = "module-workbench-execution-packet-archive"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_ENTRY_PREFIX = (
    "module-workbench-execution-packet-archive-entry"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_CHECK_PREFIX = (
    "module-workbench-execution-packet-archive-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERIFICATION_PREFIX = (
    "module-workbench-execution-packet-archive-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_CHUNK_PREFIX = (
    "module-workbench-execution-packet-archive-chunk"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_TRANSFER_PREFIX = (
    "module-workbench-execution-packet-archive-transfer"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHECKS = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNKS = 16384
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE = 65536
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNK_SIZE = 1048576


class ModuleWorkbenchExecutionPacketArchiveState(StrEnum):
    """Publication state of an archive."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveEntryKind(StrEnum):
    """Stable distinction between the packet manifest and its payloads."""

    MANIFEST = "manifest"
    ARTIFACT = "artifact"


class ModuleWorkbenchExecutionPacketArchiveCheckPlane(StrEnum):
    """Independent archive verification planes."""

    MANIFEST = "manifest"
    PATH = "path"
    BYTES = "bytes"
    ZIP = "zip"
    PACKET = "packet"
    PUBLIC = "public"
    STORAGE = "storage"


class ModuleWorkbenchExecutionPacketArchiveTransferState(StrEnum):
    """State of a resumable archive transfer receipt."""

    READY = "ready"
    PARTIAL = "partial"
    COMPLETED = "completed"
    BLOCKED = "blocked"


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


def _ordered_unique(values: tuple[str, ...], field: str, maximum: int) -> None:
    _count(len(values), field, maximum)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if len(set(values)) != len(values) or tuple(sorted(values)) != values:
        raise ValidationError(f"{field} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveEntry:
    """One deterministic member of the archive."""

    entry_id: str
    relative_path: str
    kind: ModuleWorkbenchExecutionPacketArchiveEntryKind
    media_type: str
    ordinal: int
    byte_count: int
    line_count: int
    content_address: str

    def __post_init__(self) -> None:
        _text(self.entry_id, "entry_id", 256)
        _text(self.relative_path, "relative_path", 512)
        if not _safe_path(self.relative_path):
            raise ValidationError("archive entry path is unsafe")
        if not isinstance(self.kind, ModuleWorkbenchExecutionPacketArchiveEntryKind):
            raise ValidationError("archive entry kind is invalid")
        _text(self.media_type, "media_type", 256)
        _count(self.ordinal, "ordinal")
        _count(self.byte_count, "byte_count")
        _count(self.line_count, "line_count")
        _text(self.content_address, "content_address", 512)
        if self.kind is ModuleWorkbenchExecutionPacketArchiveEntryKind.MANIFEST:
            if self.relative_path != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST:
                raise ValidationError("archive manifest entry path is invalid")
            if self.ordinal != 0:
                raise ValidationError("archive manifest entry must be first")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_packet_archive_entry(
    value: ModuleWorkbenchExecutionPacketArchiveEntry,
) -> str:
    """Address an entry descriptor independently of the archive container."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_ENTRY_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveCheck:
    """One inspectable archive verification result."""

    check_id: str
    plane: ModuleWorkbenchExecutionPacketArchiveCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchExecutionPacketArchiveCheckPlane):
            raise ValidationError("archive check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("archive check result must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_packet_archive_check(
    value: ModuleWorkbenchExecutionPacketArchiveCheck,
) -> str:
    """Address an archive check without paths or mutable state."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_CHECK_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveVerification:
    """Verification receipt that remains serializable when an archive is blocked."""

    archive_id: str
    packet_id: str
    archive_address: str
    entry_count: int
    artifact_count: int
    present_count: int
    missing_count: int
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("archive_id", "packet_id", "archive_address", "content_address"):
            _text(getattr(self, field), field, 512)
        _count(
            self.entry_count,
            "entry_count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
        )
        _count(
            self.artifact_count,
            "artifact_count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
        )
        _count(
            self.present_count,
            "present_count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
        )
        _count(
            self.missing_count,
            "missing_count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
        )
        if self.present_count + self.missing_count != self.entry_count:
            raise ValidationError("archive entry counts do not conserve")
        if (
            not self.checks
            or len(self.checks) > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHECKS
        ):
            raise ValidationError("archive checks are incomplete or excessive")
        if not isinstance(self.accepted, bool):
            raise ValidationError("archive verification acceptance must be boolean")
        ids = tuple(item.check_id for item in self.checks)
        _ordered_unique(
            ids,
            "archive check IDs",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHECKS,
        )

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "archive_id": self.archive_id,
            "packet_id": self.packet_id,
            "archive_address": self.archive_address,
            "entry_count": self.entry_count,
            "artifact_count": self.artifact_count,
            "present_count": self.present_count,
            "missing_count": self.missing_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_verification(
    value: ModuleWorkbenchExecutionPacketArchiveVerification,
) -> str:
    """Address a verification receipt."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERIFICATION_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchive:
    """A deterministic archive plus its packet and entry descriptors."""

    archive_id: str
    version: str
    boundary: str
    archive_format: str
    packet_id: str
    packet_address: str
    archive_address: str
    archive_byte_count: int
    payload_byte_count: int
    entry_count: int
    artifact_count: int
    entries: tuple[ModuleWorkbenchExecutionPacketArchiveEntry, ...]
    state: ModuleWorkbenchExecutionPacketArchiveState
    accepted: bool
    content_address: str
    archive_bytes: bytes

    def __post_init__(self) -> None:
        for field in (
            "archive_id",
            "version",
            "boundary",
            "archive_format",
            "packet_id",
            "packet_address",
            "archive_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        if self.version != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERSION:
            raise ValidationError("archive version is invalid")
        if self.boundary != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_BOUNDARY:
            raise ValidationError("archive boundary is invalid")
        if self.archive_format != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT:
            raise ValidationError("archive format is invalid")
        _count(self.archive_byte_count, "archive_byte_count")
        _count(self.payload_byte_count, "payload_byte_count")
        _count(
            self.entry_count,
            "entry_count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
        )
        _count(
            self.artifact_count,
            "artifact_count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
        )
        if not isinstance(self.archive_bytes, bytes):
            raise ValidationError("archive bytes must be bytes")
        if self.archive_byte_count != len(self.archive_bytes):
            raise ValidationError("archive byte count does not match bytes")
        if not self.entries or len(self.entries) != self.entry_count:
            raise ValidationError("archive entries do not conserve")
        if self.artifact_count != sum(
            item.kind is ModuleWorkbenchExecutionPacketArchiveEntryKind.ARTIFACT
            for item in self.entries
        ):
            raise ValidationError("archive artifact count does not conserve")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.entry_count)):
            raise ValidationError("archive entry ordinals must be contiguous")
        entry_ids = tuple(item.entry_id for item in self.entries)
        entry_paths = tuple(item.relative_path for item in self.entries)
        if len(set(entry_ids)) != len(entry_ids):
            raise ValidationError("archive entry IDs must be unique")
        if len(set(entry_paths)) != len(entry_paths):
            raise ValidationError("archive entry paths must be unique")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketArchiveState):
            raise ValidationError("archive state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("archive acceptance must be boolean")
        if self.accepted != (self.state is ModuleWorkbenchExecutionPacketArchiveState.ACCEPTED):
            raise ValidationError("archive state and acceptance do not agree")

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": self.version,
            "boundary": self.boundary,
            "archive_format": self.archive_format,
            "archive_id": self.archive_id,
            "packet_id": self.packet_id,
            "packet_address": self.packet_address,
            "archive_address": self.archive_address,
            "archive_byte_count": self.archive_byte_count,
            "payload_byte_count": self.payload_byte_count,
            "entry_count": self.entry_count,
            "artifact_count": self.artifact_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def address_module_workbench_execution_packet_archive(
    value: ModuleWorkbenchExecutionPacketArchive,
) -> str:
    """Address archive descriptors without embedding the binary container."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveChunk:
    """One addressed byte range for resumable archive transport."""

    archive_address: str
    ordinal: int
    offset: int
    byte_count: int
    content_address: str
    payload: bytes

    def __post_init__(self) -> None:
        _text(self.archive_address, "archive_address", 512)
        _count(self.ordinal, "ordinal", MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNKS)
        _count(self.offset, "offset")
        _count(
            self.byte_count,
            "byte_count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNK_SIZE,
        )
        if not isinstance(self.payload, bytes) or len(self.payload) != self.byte_count:
            raise ValidationError("archive chunk payload does not match byte count")
        _text(self.content_address, "content_address", 512)

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "archive_address": self.archive_address,
            "ordinal": self.ordinal,
            "offset": self.offset,
            "byte_count": self.byte_count,
            "content_address": self.content_address,
        }
        if include_payload:
            body["payload_hex"] = self.payload.hex()
        return body


def address_module_workbench_execution_packet_archive_chunk(
    value: ModuleWorkbenchExecutionPacketArchiveChunk,
) -> str:
    """Address chunk descriptors and exact bytes."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    body["payload_address"] = hash_bytes(
        value.payload,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_CHUNK_PREFIX,
    )
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_CHUNK_PREFIX)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveTransfer:
    """Addressed transfer plan and completion receipt."""

    transfer_id: str
    archive_id: str
    archive_address: str
    chunk_size: int
    total_byte_count: int
    total_chunks: int
    completed_chunks: tuple[int, ...]
    state: ModuleWorkbenchExecutionPacketArchiveTransferState
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.transfer_id, "transfer_id", 512)
        _text(self.archive_id, "archive_id", 512)
        _text(self.archive_address, "archive_address", 512)
        _count(
            self.chunk_size,
            "chunk_size",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNK_SIZE,
        )
        if self.chunk_size < 1:
            raise ValidationError("chunk size must be positive")
        _count(self.total_byte_count, "total_byte_count")
        _count(
            self.total_chunks,
            "total_chunks",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNKS,
        )
        _count(len(self.completed_chunks), "completed_chunks", self.total_chunks)
        if tuple(sorted(set(self.completed_chunks))) != self.completed_chunks:
            raise ValidationError("completed chunks must be sorted and unique")
        if any(item >= self.total_chunks for item in self.completed_chunks):
            raise ValidationError("completed chunk ordinal is outside transfer")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketArchiveTransferState):
            raise ValidationError("transfer state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("transfer acceptance must be boolean")
        expected = len(self.completed_chunks) == self.total_chunks
        if self.accepted != expected:
            raise ValidationError("transfer acceptance does not conserve chunks")
        if (
            self.state is ModuleWorkbenchExecutionPacketArchiveTransferState.COMPLETED
            and not expected
        ):
            raise ValidationError("completed transfer must contain every chunk")
        _text(self.content_address, "content_address", 512)

    @property
    def remaining_chunks(self) -> int:
        return self.total_chunks - len(self.completed_chunks)

    @property
    def completion_ratio(self) -> float:
        if self.total_chunks == 0:
            return 1.0
        return round(len(self.completed_chunks) / self.total_chunks, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "archive_id": self.archive_id,
            "archive_address": self.archive_address,
            "chunk_size": self.chunk_size,
            "total_byte_count": self.total_byte_count,
            "total_chunks": self.total_chunks,
            "completed_chunks": list(self.completed_chunks),
            "remaining_chunks": self.remaining_chunks,
            "completion_ratio": self.completion_ratio,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_transfer(
    value: ModuleWorkbenchExecutionPacketArchiveTransfer,
) -> str:
    """Address the transfer plan and its completion state."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_TRANSFER_PREFIX)


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_CHECK_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_CHUNK_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_ENTRY_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHECKS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNK_SIZE",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNKS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_TRANSFER_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERIFICATION_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERSION",
    "ModuleWorkbenchExecutionPacketArchive",
    "ModuleWorkbenchExecutionPacketArchiveCheck",
    "ModuleWorkbenchExecutionPacketArchiveCheckPlane",
    "ModuleWorkbenchExecutionPacketArchiveChunk",
    "ModuleWorkbenchExecutionPacketArchiveEntry",
    "ModuleWorkbenchExecutionPacketArchiveEntryKind",
    "ModuleWorkbenchExecutionPacketArchiveState",
    "ModuleWorkbenchExecutionPacketArchiveTransfer",
    "ModuleWorkbenchExecutionPacketArchiveTransferState",
    "ModuleWorkbenchExecutionPacketArchiveVerification",
    "address_module_workbench_execution_packet_archive",
    "address_module_workbench_execution_packet_archive_check",
    "address_module_workbench_execution_packet_archive_chunk",
    "address_module_workbench_execution_packet_archive_entry",
    "address_module_workbench_execution_packet_archive_transfer",
    "address_module_workbench_execution_packet_archive_verification",
]
