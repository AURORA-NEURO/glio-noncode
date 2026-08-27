"""Immutable checkpoints and ancestry comparisons for archive stores."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store import (
    verify_module_workbench_execution_packet_archive_store,
)
from .module_workbench_execution_packet_archive_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS,
    ModuleWorkbenchExecutionPacketArchiveStore,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_VERSION = (
    "module-workbench-execution-packet-archive-store-checkpoint-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_checkpoint"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_PREFIX = (
    "module-workbench-execution-packet-archive-store-checkpoint"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_COMPARISON_PREFIX = (
    "module-workbench-execution-packet-archive-store-comparison"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_QUERY_PREFIX = (
    "module-workbench-execution-packet-archive-store-checkpoint-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_MAX_LIMIT = 512


class ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreComparisonState(StrEnum):
    MATCHED = "matched"
    EXTENDED = "extended"
    DIVERGED = "diverged"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    normalized = _text(value, field)
    if ":" not in normalized:
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the supported bound")


def _addresses(values: tuple[str, ...], field: str) -> None:
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    if len(values) > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS:
        raise ValidationError(f"{field} exceeds the supported bound")
    for value in values:
        _address(value, field)


class _CheckpointBase:
    """Shared type marker for public checkpoint results."""


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint(_CheckpointBase):
    checkpoint_id: str
    version: str
    boundary: str
    store_id: str
    store_address: str
    head_address: str
    archive_count: int
    object_count: int
    operation_count: int
    total_byte_count: int
    operation_addresses: tuple[str, ...]
    entry_addresses: tuple[str, ...]
    state: ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.checkpoint_id, "checkpoint ID")
        if self.version != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_VERSION:
            raise ValidationError("checkpoint version is invalid")
        if self.boundary != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_BOUNDARY:
            raise ValidationError("checkpoint boundary is invalid")
        _text(self.store_id, "store ID")
        for value, field in (
            (self.store_address, "store address"),
            (self.head_address, "head address"),
            (self.content_address, "checkpoint address"),
        ):
            _address(value, field)
        for value, field in (
            (self.archive_count, "archive count"),
            (self.object_count, "object count"),
            (self.operation_count, "operation count"),
            (self.total_byte_count, "total byte count"),
        ):
            _count(value, field)
        if self.archive_count != self.object_count or self.archive_count != len(
            self.entry_addresses
        ):
            raise ValidationError("checkpoint archive/object counts do not conserve")
        if self.operation_count != len(self.operation_addresses):
            raise ValidationError("checkpoint operation count does not conserve")
        _addresses(self.operation_addresses, "checkpoint operation addresses")
        _addresses(self.entry_addresses, "checkpoint entry addresses")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState):
            raise ValidationError("checkpoint state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("checkpoint acceptance must be boolean")
        if self.accepted != (
            self.state is ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState.ACCEPTED
        ):
            raise ValidationError("checkpoint state and acceptance do not agree")

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "version": self.version,
            "boundary": self.boundary,
            "store_id": self.store_id,
            "store_address": self.store_address,
            "head_address": self.head_address,
            "archive_count": self.archive_count,
            "object_count": self.object_count,
            "operation_count": self.operation_count,
            "total_byte_count": self.total_byte_count,
            "operation_addresses": list(self.operation_addresses),
            "entry_addresses": list(self.entry_addresses),
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.to_dict().items()
            if key not in {"operation_addresses", "entry_addresses"}
        }


def address_module_workbench_execution_packet_archive_store_checkpoint(
    value: ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_PREFIX
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreComparison(_CheckpointBase):
    checkpoint_id: str
    store_id: str
    checkpoint_store_address: str
    current_store_address: str
    checkpoint_head_address: str
    current_head_address: str
    checkpoint_operation_count: int
    current_operation_count: int
    checkpoint_entry_count: int
    current_entry_count: int
    state: ModuleWorkbenchExecutionPacketArchiveStoreComparisonState
    ancestor: bool
    accepted: bool
    added_operation_addresses: tuple[str, ...]
    missing_operation_addresses: tuple[str, ...]
    added_entry_addresses: tuple[str, ...]
    missing_entry_addresses: tuple[str, ...]
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.checkpoint_id, "checkpoint ID")
        _text(self.store_id, "store ID")
        for value, field in (
            (self.checkpoint_store_address, "checkpoint store address"),
            (self.current_store_address, "current store address"),
            (self.checkpoint_head_address, "checkpoint head address"),
            (self.current_head_address, "current head address"),
            (self.content_address, "comparison address"),
        ):
            _address(value, field)
        for value, field in (
            (self.checkpoint_operation_count, "checkpoint operation count"),
            (self.current_operation_count, "current operation count"),
            (self.checkpoint_entry_count, "checkpoint entry count"),
            (self.current_entry_count, "current entry count"),
        ):
            _count(value, field)
        _addresses(self.added_operation_addresses, "added operation addresses")
        _addresses(self.missing_operation_addresses, "missing operation addresses")
        _addresses(self.added_entry_addresses, "added entry addresses")
        _addresses(self.missing_entry_addresses, "missing entry addresses")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketArchiveStoreComparisonState):
            raise ValidationError("comparison state is invalid")
        if not isinstance(self.ancestor, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("comparison flags must be boolean")
        _text(self.detail, "comparison detail", maximum=2048)
        if self.accepted != (
            self.state
            in {
                ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.MATCHED,
                ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.EXTENDED,
            }
        ):
            raise ValidationError("comparison state and acceptance do not agree")
        if self.ancestor != (
            self.state
            in {
                ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.MATCHED,
                ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.EXTENDED,
            }
        ):
            raise ValidationError("comparison ancestry and state do not agree")

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "store_id": self.store_id,
            "checkpoint_store_address": self.checkpoint_store_address,
            "current_store_address": self.current_store_address,
            "checkpoint_head_address": self.checkpoint_head_address,
            "current_head_address": self.current_head_address,
            "checkpoint_operation_count": self.checkpoint_operation_count,
            "current_operation_count": self.current_operation_count,
            "checkpoint_entry_count": self.checkpoint_entry_count,
            "current_entry_count": self.current_entry_count,
            "state": self.state,
            "ancestor": self.ancestor,
            "accepted": self.accepted,
            "added_operation_addresses": list(self.added_operation_addresses),
            "missing_operation_addresses": list(self.missing_operation_addresses),
            "added_entry_addresses": list(self.added_entry_addresses),
            "missing_entry_addresses": list(self.missing_entry_addresses),
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_comparison(
    value: ModuleWorkbenchExecutionPacketArchiveStoreComparison,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_COMPARISON_PREFIX
    )


def _checkpoint_body(
    store: ModuleWorkbenchExecutionPacketArchiveStore,
    checkpoint_id: str,
) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_BOUNDARY,
        "store_id": store.store_id,
        "store_address": store.content_address,
        "head_address": store.head_address,
        "archive_count": store.archive_count,
        "object_count": store.object_count,
        "operation_count": store.operation_count,
        "total_byte_count": store.total_byte_count,
        "operation_addresses": tuple(item.content_address for item in store.operations),
        "entry_addresses": tuple(item.content_address for item in store.entries),
        "state": ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState.ACCEPTED,
        "accepted": True,
    }


def build_module_workbench_execution_packet_archive_store_checkpoint(
    store: ModuleWorkbenchExecutionPacketArchiveStore,
    *,
    checkpoint_id: str = "glio-noncode-module-workbench-execution-archive-store-checkpoint",
) -> ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint:
    """Capture an immutable addressed journal and entry boundary."""

    verification = verify_module_workbench_execution_packet_archive_store(store)
    if not verification.accepted:
        raise ValidationError("checkpoint requires an accepted archive store")
    body = _checkpoint_body(store, checkpoint_id)
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint(
        **body,
        content_address="pending:checkpoint",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_checkpoint(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_checkpoint(
    value: ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint,
) -> ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint:
    """Verify checkpoint type, counts, and deterministic address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint):
        raise ValidationError("checkpoint verification requires a typed checkpoint")
    expected = address_module_workbench_execution_packet_archive_store_checkpoint(value)
    if value.content_address != expected:
        raise ValidationError("checkpoint address mismatch")
    return value


def checkpoint_module_workbench_execution_packet_archive_store_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint:
    """Rehydrate and verify a checkpoint exported as canonical JSON."""

    if not isinstance(value, Mapping):
        raise ValidationError("checkpoint document must be an object")
    body = dict(value)
    body["operation_addresses"] = tuple(body.get("operation_addresses", ()))
    body["entry_addresses"] = tuple(body.get("entry_addresses", ()))
    body["state"] = ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState(body["state"])
    checkpoint = ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint(**body)
    return verify_module_workbench_execution_packet_archive_store_checkpoint(checkpoint)


def compare_module_workbench_execution_packet_archive_store_to_checkpoint(
    store: ModuleWorkbenchExecutionPacketArchiveStore,
    checkpoint: ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint,
) -> ModuleWorkbenchExecutionPacketArchiveStoreComparison:
    """Prove whether a current store matches or extends a checkpoint."""

    store_verification = verify_module_workbench_execution_packet_archive_store(store)
    verify_module_workbench_execution_packet_archive_store_checkpoint(checkpoint)
    current_operations = tuple(item.content_address for item in store.operations)
    current_entries = tuple(item.content_address for item in store.entries)
    operations_prefix = (
        current_operations[: checkpoint.operation_count] == checkpoint.operation_addresses
    )
    entries_prefix = current_entries[: checkpoint.archive_count] == checkpoint.entry_addresses
    same_store = store.store_id == checkpoint.store_id
    ancestor = operations_prefix and entries_prefix and same_store
    same = (
        ancestor
        and current_operations == checkpoint.operation_addresses
        and current_entries == checkpoint.entry_addresses
    )
    if not store_verification.accepted or not checkpoint.accepted or not same_store:
        state = ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.BLOCKED
        detail = "store and checkpoint cannot be compared as one accepted lineage"
    elif not ancestor:
        state = ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.DIVERGED
        detail = "current journal or entry sequence diverges from checkpoint"
    elif same:
        state = ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.MATCHED
        detail = "current store exactly matches checkpoint"
    else:
        state = ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.EXTENDED
        detail = "current store extends checkpoint with an append-only suffix"
    added_operations = tuple(
        item for item in current_operations if item not in checkpoint.operation_addresses
    )
    missing_operations = tuple(
        item for item in checkpoint.operation_addresses if item not in current_operations
    )
    added_entries = tuple(
        item for item in current_entries if item not in checkpoint.entry_addresses
    )
    missing_entries = tuple(
        item for item in checkpoint.entry_addresses if item not in current_entries
    )
    body = {
        "checkpoint_id": checkpoint.checkpoint_id,
        "store_id": store.store_id,
        "checkpoint_store_address": checkpoint.store_address,
        "current_store_address": store.content_address,
        "checkpoint_head_address": checkpoint.head_address,
        "current_head_address": store.head_address,
        "checkpoint_operation_count": checkpoint.operation_count,
        "current_operation_count": store.operation_count,
        "checkpoint_entry_count": checkpoint.archive_count,
        "current_entry_count": store.archive_count,
        "state": state,
        "ancestor": ancestor,
        "accepted": state
        in {
            ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.MATCHED,
            ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.EXTENDED,
        },
        "added_operation_addresses": added_operations,
        "missing_operation_addresses": missing_operations,
        "added_entry_addresses": added_entries,
        "missing_entry_addresses": missing_entries,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreComparison(
        **body,
        content_address="pending:comparison",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreComparison(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_comparison(
            provisional
        ),
    )


def _page(
    rows: list[dict[str, Any]], *, offset: int, limit: int, text: str | None
) -> tuple[list[dict[str, Any]], int]:
    if (
        offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_MAX_LIMIT
    ):
        raise ValidationError("checkpoint query paging is invalid")
    filtered = rows
    if text:
        needle = text.casefold()
        filtered = [item for item in rows if needle in canonical_json(item).casefold()]
    return filtered[offset : offset + limit], len(filtered)


def query_module_workbench_execution_packet_archive_store_checkpoint(
    value: ModuleWorkbenchExecutionPacketArchiveStoreComparison,
    *,
    resource: str = "summary",
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded reconciliation rows from a checkpoint comparison."""

    verify_module_workbench_execution_packet_archive_store_comparison(value)
    normalized = resource.casefold().strip()
    row_map = {
        "summary": [value.to_dict()],
        "added_operations": [{"address": item} for item in value.added_operation_addresses],
        "missing_operations": [{"address": item} for item in value.missing_operation_addresses],
        "added_entries": [{"address": item} for item in value.added_entry_addresses],
        "missing_entries": [{"address": item} for item in value.missing_entry_addresses],
    }
    if normalized not in row_map:
        raise ValidationError("unsupported checkpoint comparison resource")
    items, total = _page(row_map[normalized], offset=offset, limit=limit, text=text)
    body = {
        "checkpoint_id": value.checkpoint_id,
        "comparison_address": value.content_address,
        "resource": normalized,
        "query": {"text": text},
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": "content_address",
        "items": items,
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_QUERY_PREFIX
        )
    }


def verify_module_workbench_execution_packet_archive_store_comparison(
    value: ModuleWorkbenchExecutionPacketArchiveStoreComparison,
) -> ModuleWorkbenchExecutionPacketArchiveStoreComparison:
    """Verify an addressed checkpoint comparison."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreComparison):
        raise ValidationError("comparison verification requires a typed comparison")
    expected = address_module_workbench_execution_packet_archive_store_comparison(value)
    if value.content_address != expected:
        raise ValidationError("comparison address mismatch")
    return value


def module_workbench_execution_packet_archive_store_checkpoint_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint,
) -> str:
    verify_module_workbench_execution_packet_archive_store_checkpoint(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_comparison_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreComparison,
) -> str:
    verify_module_workbench_execution_packet_archive_store_comparison(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_checkpoint_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint,
) -> str:
    verify_module_workbench_execution_packet_archive_store_checkpoint(value)
    fields = (
        "checkpoint_id",
        "store_id",
        "store_address",
        "head_address",
        "archive_count",
        "operation_count",
        "total_byte_count",
        "accepted",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.to_dict())
    return output.getvalue()


def module_workbench_execution_packet_archive_store_comparison_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreComparison,
) -> str:
    verify_module_workbench_execution_packet_archive_store_comparison(value)
    fields = ("resource", "address", "state", "accepted", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for resource, addresses in (
        ("added_operation", value.added_operation_addresses),
        ("missing_operation", value.missing_operation_addresses),
        ("added_entry", value.added_entry_addresses),
        ("missing_entry", value.missing_entry_addresses),
    ):
        for address in addresses:
            writer.writerow(
                {
                    "resource": resource,
                    "address": address,
                    "state": value.state,
                    "accepted": value.accepted,
                    "content_address": value.content_address,
                }
            )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_checkpoint_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint,
) -> str:
    verify_module_workbench_execution_packet_archive_store_checkpoint(value)
    return "\n".join(
        (
            "# Archive Store Checkpoint",
            "",
            f"- Checkpoint: `{value.checkpoint_id}`",
            f"- Store: `{value.store_id}`",
            f"- Store address: `{value.store_address}`",
            f"- Head: `{value.head_address}`",
            f"- Archives / objects / operations: `{value.archive_count}` / "
            f"`{value.object_count}` / `{value.operation_count}`",
            f"- Total bytes: `{value.total_byte_count:,}`",
            f"- Accepted: `{str(value.accepted).lower()}`",
            f"- Address: `{value.content_address}`",
            "",
        )
    )


def module_workbench_execution_packet_archive_store_checkpoint_schema() -> dict[str, Any]:
    """Describe checkpoint and ancestry resources."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_BOUNDARY,
        "states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState
        ],
        "comparison_states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreComparisonState
        ],
        "resources": [
            "summary",
            "added_operations",
            "missing_operations",
            "added_entries",
            "missing_entries",
        ],
        "inputs": ["accepted_store", "checkpoint"],
        "outputs": ["checkpoint", "comparison", "query", "json", "csv", "markdown"],
        "max_operation_addresses": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_OPERATIONS,
        "identity_free": True,
        "timestamp_free": True,
        "path_free": True,
    }


def module_workbench_execution_packet_archive_store_checkpoint_capabilities() -> dict[str, Any]:
    """Declare checkpoint, ancestry, and reconciliation operations."""

    operations = (
        "capture_checkpoint",
        "address_checkpoint",
        "verify_checkpoint",
        "compare_store_to_checkpoint",
        "prove_append_only_ancestry",
        "detect_journal_divergence",
        "detect_missing_operations",
        "detect_added_operations",
        "detect_missing_entries",
        "detect_added_entries",
        "query_comparison_summary",
        "query_added_operations",
        "query_missing_operations",
        "query_added_entries",
        "query_missing_entries",
        "export_checkpoint_json",
        "export_checkpoint_csv",
        "export_checkpoint_markdown",
        "export_comparison_json",
        "export_comparison_csv",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only": True,
        "deterministic": True,
        "append_only_proof": True,
        "identity_free": True,
    }


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_QUERY_PREFIX",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_CHECKPOINT_VERSION",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_COMPARISON_PREFIX",
    "ModuleWorkbenchExecutionPacketArchiveStoreCheckpoint",
    "ModuleWorkbenchExecutionPacketArchiveStoreCheckpointState",
    "ModuleWorkbenchExecutionPacketArchiveStoreComparison",
    "ModuleWorkbenchExecutionPacketArchiveStoreComparisonState",
    "address_module_workbench_execution_packet_archive_store_checkpoint",
    "address_module_workbench_execution_packet_archive_store_comparison",
    "build_module_workbench_execution_packet_archive_store_checkpoint",
    "checkpoint_module_workbench_execution_packet_archive_store_from_mapping",
    "compare_module_workbench_execution_packet_archive_store_to_checkpoint",
    "module_workbench_execution_packet_archive_store_checkpoint_capabilities",
    "module_workbench_execution_packet_archive_store_checkpoint_csv",
    "module_workbench_execution_packet_archive_store_checkpoint_json",
    "module_workbench_execution_packet_archive_store_checkpoint_schema",
    "module_workbench_execution_packet_archive_store_comparison_csv",
    "module_workbench_execution_packet_archive_store_comparison_json",
    "query_module_workbench_execution_packet_archive_store_checkpoint",
    "render_module_workbench_execution_packet_archive_store_checkpoint_markdown",
    "verify_module_workbench_execution_packet_archive_store_checkpoint",
    "verify_module_workbench_execution_packet_archive_store_comparison",
]
