"""Compare deterministic execution packet archives without source access."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
    load_module_workbench_execution_packet_archive,
    verify_module_workbench_execution_packet_archive_value,
)
from .module_workbench_execution_packet_archive_contracts import (
    ModuleWorkbenchExecutionPacketArchive,
    ModuleWorkbenchExecutionPacketArchiveEntry,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_VERSION = (
    "module-workbench-execution-packet-archive-diff-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_diff"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_MAX_LIMIT = 512
_RESOURCE_NAMES = ("summary", "changes", "added", "removed", "modified", "unchanged")
_CHANGE_KINDS = ("added", "removed", "modified", "unchanged")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"archive diff {field} is required")
    return value


def _archive(
    value: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
) -> ModuleWorkbenchExecutionPacketArchive:
    if isinstance(value, ModuleWorkbenchExecutionPacketArchive):
        verify_module_workbench_execution_packet_archive_value(value)
        return value
    return build_module_workbench_execution_packet_archive(
        load_module_workbench_execution_packet_archive(value)
    )


def _entry_row(
    change: str,
    path: str,
    left: ModuleWorkbenchExecutionPacketArchiveEntry | None,
    right: ModuleWorkbenchExecutionPacketArchiveEntry | None,
) -> dict[str, Any]:
    left_body = left.to_dict() if left is not None else None
    right_body = right.to_dict() if right is not None else None
    left_bytes = left.byte_count if left is not None else 0
    right_bytes = right.byte_count if right is not None else 0
    return {
        "change": change,
        "relative_path": path,
        "entry_id": right.entry_id if right is not None else left.entry_id,
        "kind": (right.kind if right is not None else left.kind),
        "left": left_body,
        "right": right_body,
        "left_byte_count": left_bytes,
        "right_byte_count": right_bytes,
        "byte_delta": right_bytes - left_bytes,
        "content_changed": change != "unchanged",
    }


def _address_diff(value: ModuleWorkbenchExecutionPacketArchiveDiff) -> str:
    body = {
        key: item
        for key, item in value.to_dict(include_changes=True).items()
        if key != "content_address"
    }
    return content_hash(body, prefix="module-workbench-execution-packet-archive-diff")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveDiff:
    """Addressed reconciliation report for two exact archive containers."""

    left_archive_id: str
    right_archive_id: str
    left_archive_address: str
    right_archive_address: str
    left_packet_address: str
    right_packet_address: str
    left_archive_byte_count: int
    right_archive_byte_count: int
    left_payload_byte_count: int
    right_payload_byte_count: int
    left_entry_count: int
    right_entry_count: int
    changes: tuple[dict[str, Any], ...]
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    same_archive_bytes: bool
    same_packet: bool
    same_format: bool
    byte_delta: int
    payload_byte_delta: int
    entry_delta: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "left_archive_id",
            "right_archive_id",
            "left_archive_address",
            "right_archive_address",
            "left_packet_address",
            "right_packet_address",
            "content_address",
        ):
            _text(getattr(self, field), field)
        numeric = (
            "left_archive_byte_count",
            "right_archive_byte_count",
            "left_payload_byte_count",
            "right_payload_byte_count",
            "left_entry_count",
            "right_entry_count",
            "added_count",
            "removed_count",
            "modified_count",
            "unchanged_count",
        )
        for field in numeric:
            value = getattr(self, field)
            if not isinstance(value, int) or value < 0:
                raise ValidationError(f"archive diff {field} is invalid")
        for field in ("byte_delta", "payload_byte_delta", "entry_delta"):
            if not isinstance(getattr(self, field), int):
                raise ValidationError(f"archive diff {field} is invalid")
        for field in ("same_archive_bytes", "same_packet", "same_format", "accepted"):
            if not isinstance(getattr(self, field), bool):
                raise ValidationError(f"archive diff {field} must be boolean")
        if self.left_entry_count != self.removed_count + self.modified_count + self.unchanged_count:
            raise ValidationError("left archive entry counts do not conserve")
        if self.right_entry_count != self.added_count + self.modified_count + self.unchanged_count:
            raise ValidationError("right archive entry counts do not conserve")
        if len(self.changes) != (
            self.added_count + self.removed_count + self.modified_count + self.unchanged_count
        ):
            raise ValidationError("archive diff changes do not conserve")
        if self.byte_delta != self.right_archive_byte_count - self.left_archive_byte_count:
            raise ValidationError("archive diff byte delta is inconsistent")
        if self.payload_byte_delta != self.right_payload_byte_count - self.left_payload_byte_count:
            raise ValidationError("archive diff payload delta is inconsistent")
        if self.entry_delta != self.right_entry_count - self.left_entry_count:
            raise ValidationError("archive diff entry delta is inconsistent")
        paths = tuple(row.get("relative_path") for row in self.changes)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValidationError("archive diff paths must be sorted and unique")

    @property
    def change_count(self) -> int:
        return len(self.changes)

    @property
    def identical(self) -> bool:
        return self.same_archive_bytes

    @property
    def compatible(self) -> bool:
        return self.same_format and self.same_packet

    def to_dict(self, *, include_changes: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_BOUNDARY,
            "left_archive_id": self.left_archive_id,
            "right_archive_id": self.right_archive_id,
            "left_archive_address": self.left_archive_address,
            "right_archive_address": self.right_archive_address,
            "left_packet_address": self.left_packet_address,
            "right_packet_address": self.right_packet_address,
            "left_archive_byte_count": self.left_archive_byte_count,
            "right_archive_byte_count": self.right_archive_byte_count,
            "left_payload_byte_count": self.left_payload_byte_count,
            "right_payload_byte_count": self.right_payload_byte_count,
            "left_entry_count": self.left_entry_count,
            "right_entry_count": self.right_entry_count,
            "change_count": self.change_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "modified_count": self.modified_count,
            "unchanged_count": self.unchanged_count,
            "same_archive_bytes": self.same_archive_bytes,
            "same_packet": self.same_packet,
            "same_format": self.same_format,
            "compatible": self.compatible,
            "identical": self.identical,
            "byte_delta": self.byte_delta,
            "payload_byte_delta": self.payload_byte_delta,
            "entry_delta": self.entry_delta,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_changes:
            body["changes"] = list(self.changes)
        return body


def diff_module_workbench_execution_packet_archives(
    left: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
    right: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveDiff:
    """Compare archive members and exact container bytes deterministically."""

    left_archive = _archive(left)
    right_archive = _archive(right)
    left_entries = {item.relative_path: item for item in left_archive.entries}
    right_entries = {item.relative_path: item for item in right_archive.entries}
    changes: list[dict[str, Any]] = []
    added = removed = modified = unchanged = 0
    for path in sorted(set(left_entries) | set(right_entries)):
        left_entry = left_entries.get(path)
        right_entry = right_entries.get(path)
        if left_entry is None:
            kind = "added"
            added += 1
        elif right_entry is None:
            kind = "removed"
            removed += 1
        elif (
            left_entry.content_address != right_entry.content_address
            or left_entry.kind != right_entry.kind
            or left_entry.byte_count != right_entry.byte_count
        ):
            kind = "modified"
            modified += 1
        else:
            kind = "unchanged"
            unchanged += 1
        changes.append(_entry_row(kind, path, left_entry, right_entry))
    body = {
        "left_archive_id": left_archive.archive_id,
        "right_archive_id": right_archive.archive_id,
        "left_archive_address": left_archive.archive_address,
        "right_archive_address": right_archive.archive_address,
        "left_packet_address": left_archive.packet_address,
        "right_packet_address": right_archive.packet_address,
        "left_archive_byte_count": left_archive.archive_byte_count,
        "right_archive_byte_count": right_archive.archive_byte_count,
        "left_payload_byte_count": left_archive.payload_byte_count,
        "right_payload_byte_count": right_archive.payload_byte_count,
        "left_entry_count": left_archive.entry_count,
        "right_entry_count": right_archive.entry_count,
        "changes": tuple(changes),
        "added_count": added,
        "removed_count": removed,
        "modified_count": modified,
        "unchanged_count": unchanged,
        "same_archive_bytes": left_archive.archive_bytes == right_archive.archive_bytes,
        "same_packet": left_archive.packet_address == right_archive.packet_address,
        "same_format": left_archive.archive_format == right_archive.archive_format,
        "byte_delta": right_archive.archive_byte_count - left_archive.archive_byte_count,
        "payload_byte_delta": right_archive.payload_byte_count - left_archive.payload_byte_count,
        "entry_delta": right_archive.entry_count - left_archive.entry_count,
        "accepted": left_archive.accepted and right_archive.accepted,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveDiff(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveDiff(
        **body,
        content_address=_address_diff(provisional),
    )


def verify_module_workbench_execution_packet_archive_diff(
    value: ModuleWorkbenchExecutionPacketArchiveDiff,
) -> ModuleWorkbenchExecutionPacketArchiveDiff:
    """Verify conservation, compatibility flags, and the report address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveDiff):
        raise ValidationError("archive diff verification requires a typed diff")
    if _address_diff(value) != value.content_address:
        raise ValidationError("archive diff content address mismatch")
    return value


def _page(
    rows: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    text: str | None,
) -> tuple[list[dict[str, Any]], int]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_MAX_LIMIT:
        raise ValidationError("archive diff query paging is invalid")
    filtered = rows
    if text:
        needle = text.casefold()
        filtered = [row for row in rows if needle in canonical_json(row).casefold()]
    return filtered[offset : offset + limit], len(filtered)


def query_module_workbench_execution_packet_archive_diff(
    value: ModuleWorkbenchExecutionPacketArchiveDiff,
    *,
    resource: str = "changes",
    change: str | None = None,
    relative_path: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded reconciliation rows with optional indexed filters."""

    verify_module_workbench_execution_packet_archive_diff(value)
    normalized = resource.casefold().strip()
    if normalized not in _RESOURCE_NAMES:
        raise ValidationError("unsupported archive diff resource")
    if change is not None and change not in _CHANGE_KINDS:
        raise ValidationError("unsupported archive diff change filter")
    if normalized == "summary":
        rows = [value.to_dict(include_changes=False)]
        index_used = "archive_address"
    else:
        rows = list(value.changes)
        if normalized != "changes":
            rows = [row for row in rows if row.get("change") == normalized]
        if change is not None:
            rows = [row for row in rows if row.get("change") == change]
        if relative_path:
            rows = [row for row in rows if row.get("relative_path") == relative_path]
        if kind:
            rows = [row for row in rows if row.get("kind") == kind]
        index_used = "relative_path"
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    body = {
        "resource": normalized,
        "left_archive_address": value.left_archive_address,
        "right_archive_address": value.right_archive_address,
        "query": {
            "change": change,
            "relative_path": relative_path,
            "kind": kind,
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
            prefix="module-workbench-execution-packet-archive-diff-query",
        )
    }


def module_workbench_execution_packet_archive_diff_json(
    value: ModuleWorkbenchExecutionPacketArchiveDiff,
) -> str:
    """Return canonical JSON for an archive reconciliation report."""

    verify_module_workbench_execution_packet_archive_diff(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_diff_csv(
    value: ModuleWorkbenchExecutionPacketArchiveDiff,
) -> str:
    """Return one deterministic CSV row per changed or unchanged member."""

    verify_module_workbench_execution_packet_archive_diff(value)
    fields = (
        "change",
        "relative_path",
        "entry_id",
        "kind",
        "left_byte_count",
        "right_byte_count",
        "byte_delta",
        "content_changed",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value.changes:
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_diff_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveDiff,
) -> str:
    """Render a compact review table while retaining stable member paths."""

    verify_module_workbench_execution_packet_archive_diff(value)
    lines = [
        "# Module Workbench Execution Packet Archive Diff",
        "",
        f"- Left: `{value.left_archive_address}`",
        f"- Right: `{value.right_archive_address}`",
        f"- Compatible: `{str(value.compatible).lower()}`",
        f"- Identical bytes: `{str(value.identical).lower()}`",
        f"- Added / removed / modified / unchanged: `{value.added_count}` / "
        f"`{value.removed_count}` / `{value.modified_count}` / `{value.unchanged_count}`",
        f"- Archive byte delta: `{value.byte_delta:+,}`",
        "",
        "| Change | Path | Kind | Left bytes | Right bytes | Delta |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in value.changes:
        lines.append(
            f"| `{row['change']}` | `{row['relative_path']}` | `{row['kind']}` | "
            f"{row['left_byte_count']:,} | {row['right_byte_count']:,} | {row['byte_delta']:+,} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_diff_schema() -> dict[str, Any]:
    """Describe archive reconciliation resources and conservation rules."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_BOUNDARY,
        "resources": list(_RESOURCE_NAMES),
        "change_kinds": list(_CHANGE_KINDS),
        "filters": ["change", "relative_path", "kind", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_MAX_LIMIT,
        },
        "inputs": ["typed_archive", "archive_bytes", "archive_path"],
        "outputs": ["member_changes", "byte_deltas", "compatibility_flags", "addressed_report"],
        "conservation": ["archive_bytes", "payload_bytes", "entry_counts", "member_paths"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_diff_capabilities() -> dict[str, Any]:
    """Declare read-only archive reconciliation operations."""

    operations = (
        "compare_archive_bytes",
        "compare_packet_addresses",
        "compare_archive_formats",
        "classify_added_members",
        "classify_removed_members",
        "classify_modified_members",
        "classify_unchanged_members",
        "calculate_archive_byte_delta",
        "calculate_payload_byte_delta",
        "calculate_entry_delta",
        "query_change_rows",
        "filter_change_kind",
        "filter_relative_path",
        "filter_entry_kind",
        "page_change_rows",
        "verify_report_address",
        "export_json",
        "export_csv",
        "export_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only": True,
        "deterministic": True,
        "identity_free": True,
    }


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DIFF_VERSION",
    "ModuleWorkbenchExecutionPacketArchiveDiff",
    "diff_module_workbench_execution_packet_archives",
    "module_workbench_execution_packet_archive_diff_capabilities",
    "module_workbench_execution_packet_archive_diff_csv",
    "module_workbench_execution_packet_archive_diff_json",
    "module_workbench_execution_packet_archive_diff_schema",
    "query_module_workbench_execution_packet_archive_diff",
    "render_module_workbench_execution_packet_archive_diff_markdown",
    "verify_module_workbench_execution_packet_archive_diff",
]
