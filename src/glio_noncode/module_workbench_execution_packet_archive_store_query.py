"""Bounded queries, diffs, and exports for archive stores."""

from __future__ import annotations

import csv
import io
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store import (
    verify_module_workbench_execution_packet_archive_store,
)
from .module_workbench_execution_packet_archive_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStore,
)
from .serialization import canonical_json, content_hash

_RESOURCE_NAMES = ("summary", "entries", "operations")
_DIFF_RESOURCE_NAMES = ("summary", "entries", "operations")


def _page(
    rows: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    text: str | None,
) -> tuple[list[dict[str, Any]], int]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_LIMIT:
        raise ValidationError("archive store query paging is invalid")
    filtered = rows
    if text:
        needle = text.casefold()
        filtered = [item for item in rows if needle in canonical_json(item).casefold()]
    return filtered[offset : offset + limit], len(filtered)


def query_module_workbench_execution_packet_archive_store(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
    *,
    resource: str = "entries",
    archive_address: str | None = None,
    operation_id: str | None = None,
    kind: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded store summary, entry, or journal rows."""

    verification = verify_module_workbench_execution_packet_archive_store(value)
    if not verification.accepted:
        raise ValidationError("archive store query requires an accepted store")
    normalized = resource.casefold().strip()
    if normalized not in _RESOURCE_NAMES:
        raise ValidationError("unsupported archive store resource")
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "store_id"
    elif normalized == "operations":
        rows = [item.to_dict() for item in value.operations]
        if archive_address:
            rows = [item for item in rows if item.get("archive_address") == archive_address]
        if operation_id:
            rows = [item for item in rows if item.get("operation_id") == operation_id]
        if kind:
            rows = [item for item in rows if item.get("kind") == kind]
        if accepted is not None:
            rows = [item for item in rows if item.get("accepted") is accepted]
        index_used = "operation_id"
    else:
        rows = [item.to_dict() for item in value.entries]
        if archive_address:
            rows = [item for item in rows if item.get("archive_address") == archive_address]
        if accepted is not None:
            rows = [item for item in rows if item.get("accepted") is accepted]
        index_used = "archive_address"
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    body = {
        "store_id": value.store_id,
        "store_address": value.content_address,
        "resource": normalized,
        "query": {
            "archive_address": archive_address,
            "operation_id": operation_id,
            "kind": kind,
            "accepted": accepted,
            "text": text,
        },
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": items,
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-archive-store-query",
        )
    }


def diff_module_workbench_execution_packet_archive_stores(
    left: ModuleWorkbenchExecutionPacketArchiveStore,
    right: ModuleWorkbenchExecutionPacketArchiveStore,
) -> dict[str, Any]:
    """Compare store entries, journals, heads, and byte totals."""

    for store in (left, right):
        verification = verify_module_workbench_execution_packet_archive_store(store)
        if not verification.accepted:
            raise ValidationError("archive store diff requires accepted stores")
    left_entries = {item.archive_address: item for item in left.entries}
    right_entries = {item.archive_address: item for item in right.entries}
    left_operations = {item.operation_id: item for item in left.operations}
    right_operations = {item.operation_id: item for item in right.operations}
    entry_rows: list[dict[str, Any]] = []
    for archive_address in sorted(set(left_entries) | set(right_entries)):
        left_entry = left_entries.get(archive_address)
        right_entry = right_entries.get(archive_address)
        if left_entry is None:
            change = "added"
        elif right_entry is None:
            change = "removed"
        elif left_entry.content_address != right_entry.content_address:
            change = "modified"
        else:
            change = "unchanged"
        entry_rows.append(
            {
                "change": change,
                "archive_address": archive_address,
                "left": left_entry.to_dict() if left_entry is not None else None,
                "right": right_entry.to_dict() if right_entry is not None else None,
            }
        )
    operation_rows: list[dict[str, Any]] = []
    for operation_id in sorted(set(left_operations) | set(right_operations)):
        left_operation = left_operations.get(operation_id)
        right_operation = right_operations.get(operation_id)
        if left_operation is None:
            change = "added"
        elif right_operation is None:
            change = "removed"
        elif left_operation.content_address != right_operation.content_address:
            change = "modified"
        else:
            change = "unchanged"
        operation_rows.append(
            {
                "change": change,
                "operation_id": operation_id,
                "left": left_operation.to_dict() if left_operation is not None else None,
                "right": right_operation.to_dict() if right_operation is not None else None,
            }
        )
    body = {
        "left_store_id": left.store_id,
        "right_store_id": right.store_id,
        "left_store_address": left.content_address,
        "right_store_address": right.content_address,
        "left_head_address": left.head_address,
        "right_head_address": right.head_address,
        "left_archive_count": left.archive_count,
        "right_archive_count": right.archive_count,
        "left_operation_count": left.operation_count,
        "right_operation_count": right.operation_count,
        "left_total_byte_count": left.total_byte_count,
        "right_total_byte_count": right.total_byte_count,
        "entry_change_count": len(entry_rows),
        "operation_change_count": len(operation_rows),
        "added_archive_count": sum(item["change"] == "added" for item in entry_rows),
        "removed_archive_count": sum(item["change"] == "removed" for item in entry_rows),
        "modified_archive_count": sum(item["change"] == "modified" for item in entry_rows),
        "unchanged_archive_count": sum(item["change"] == "unchanged" for item in entry_rows),
        "head_changed": left.head_address != right.head_address,
        "same_store": left.content_address == right.content_address,
        "same_objects": tuple(item.archive_address for item in left.entries)
        == tuple(item.archive_address for item in right.entries),
        "entry_changes": entry_rows,
        "operation_changes": operation_rows,
        "accepted": left.accepted and right.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-archive-store-diff",
        )
    }


def verify_module_workbench_execution_packet_archive_store_diff(
    value: dict[str, Any],
) -> dict[str, Any]:
    """Verify a serialized store diff's addressed body and conservation counts."""

    if not isinstance(value, dict) or not isinstance(value.get("content_address"), str):
        raise ValidationError("archive store diff must be an addressed object")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(body, prefix="module-workbench-execution-packet-archive-store-diff")
    if expected != value["content_address"]:
        raise ValidationError("archive store diff address mismatch")
    if value.get("entry_change_count") != len(value.get("entry_changes", ())):
        raise ValidationError("archive store diff entry count does not conserve")
    if value.get("operation_change_count") != len(value.get("operation_changes", ())):
        raise ValidationError("archive store diff operation count does not conserve")
    return value


def module_workbench_execution_packet_archive_store_json(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
) -> str:
    """Return canonical full store JSON without binary objects."""

    verification = verify_module_workbench_execution_packet_archive_store(value)
    if not verification.accepted:
        raise ValidationError("cannot export a blocked archive store")
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
) -> str:
    """Return one deterministic row per archive store entry."""

    verification = verify_module_workbench_execution_packet_archive_store(value)
    if not verification.accepted:
        raise ValidationError("cannot export a blocked archive store")
    fields = (
        "ordinal",
        "archive_id",
        "packet_id",
        "archive_address",
        "packet_address",
        "object_key",
        "byte_count",
        "state",
        "accepted",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for entry in value.entries:
        writer.writerow(entry.to_dict())
    return output.getvalue()


def module_workbench_execution_packet_archive_store_diff_csv(
    value: dict[str, Any],
) -> str:
    """Return one deterministic row per changed or unchanged archive."""

    verify_module_workbench_execution_packet_archive_store_diff(value)
    fields = ("change", "archive_address", "left", "right")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value["entry_changes"]:
        writer.writerow(
            {
                "change": row["change"],
                "archive_address": row["archive_address"],
                "left": canonical_json(row["left"]),
                "right": canonical_json(row["right"]),
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStore,
) -> str:
    """Render a store catalog for review."""

    verification = verify_module_workbench_execution_packet_archive_store(value)
    if not verification.accepted:
        raise ValidationError("cannot render a blocked archive store")
    lines = [
        "# Module Workbench Execution Packet Archive Store",
        "",
        f"- Store: `{value.store_id}`",
        f"- Address: `{value.content_address}`",
        f"- Head: `{value.head_address}`",
        f"- Archives / objects / operations: `{value.archive_count}` / "
        f"`{value.object_count}` / `{value.operation_count}`",
        f"- Total bytes: `{value.total_byte_count:,}`",
        f"- Deduplicated registrations: `{value.duplicate_registration_count}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "| Ordinal | Archive | Packet | Bytes | Object | Accepted |",
        "|---:|---|---|---:|---|---|",
    ]
    for entry in value.entries:
        lines.append(
            f"| {entry.ordinal} | `{entry.archive_address}` | `{entry.packet_address}` | "
            f"{entry.byte_count:,} | `{entry.object_key}` | `{str(entry.accepted).lower()}` |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_schema() -> dict[str, Any]:
    """Describe durable archive store resources and storage guarantees."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION,
        "resources": list(_RESOURCE_NAMES),
        "diff_resources": list(_DIFF_RESOURCE_NAMES),
        "filters": ["archive_address", "operation_id", "kind", "accepted", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_MAX_LIMIT,
        },
        "inputs": ["typed_store", "store_directory"],
        "outputs": ["manifest", "object_catalog", "operation_journal", "verification", "replay"],
        "storage": ["canonical_manifest_json", "objects_directory", "atomic_directory_replace"],
        "retains_binary_payloads": False,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_capabilities() -> dict[str, Any]:
    """Declare durable store, query, diff, and export operations."""

    operations = (
        "build_store",
        "deduplicate_archive_bytes",
        "write_store_atomically",
        "load_store_fail_closed",
        "verify_store_manifest",
        "verify_store_objects",
        "verify_store_operation_addresses",
        "verify_store_journal_chain",
        "verify_store_public_boundary",
        "append_store_registration",
        "append_store_batch",
        "enforce_expected_head",
        "replay_store_objects",
        "query_store_summary",
        "query_store_entries",
        "query_store_operations",
        "filter_archive_address",
        "filter_operation_id",
        "filter_operation_kind",
        "filter_acceptance",
        "page_store_rows",
        "diff_store_entries",
        "diff_store_operations",
        "compare_store_heads",
        "export_store_json",
        "export_store_csv",
        "export_store_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only_queries": True,
        "immutable_results": True,
        "atomic_writes": True,
        "deduplicated": True,
        "replayable": True,
        "identity_free": True,
    }


__all__ = [
    "diff_module_workbench_execution_packet_archive_stores",
    "module_workbench_execution_packet_archive_store_capabilities",
    "module_workbench_execution_packet_archive_store_csv",
    "module_workbench_execution_packet_archive_store_diff_csv",
    "module_workbench_execution_packet_archive_store_json",
    "module_workbench_execution_packet_archive_store_schema",
    "query_module_workbench_execution_packet_archive_store",
    "render_module_workbench_execution_packet_archive_store_markdown",
    "verify_module_workbench_execution_packet_archive_store_diff",
]
