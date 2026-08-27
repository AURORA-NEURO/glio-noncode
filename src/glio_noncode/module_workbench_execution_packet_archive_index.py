"""Build a portable, path-free index over deterministic packet archives."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
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
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_VERSION = (
    "module-workbench-execution-packet-archive-index-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_index"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_ENTRIES = 4096
_RESOURCE_NAMES = ("summary", "archives", "packets", "duplicates")


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"archive index {field} is required")
    return value


def _nonnegative(value: Any, field: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValidationError(f"archive index {field} must be a non-negative integer")
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


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveIndexEntry:
    """Path-free catalog record for one verified archive."""

    ordinal: int
    archive_id: str
    packet_id: str
    archive_address: str
    packet_address: str
    archive_byte_count: int
    payload_byte_count: int
    entry_count: int
    artifact_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _nonnegative(self.ordinal, "ordinal")
        for field in (
            "archive_id",
            "packet_id",
            "archive_address",
            "packet_address",
            "content_address",
        ):
            _required_text(getattr(self, field), field)
        for field in (
            "archive_byte_count",
            "payload_byte_count",
            "entry_count",
            "artifact_count",
        ):
            _nonnegative(getattr(self, field), field)
        if not isinstance(self.accepted, bool):
            raise ValidationError("archive index entry acceptance must be boolean")
        if self.artifact_count > self.entry_count:
            raise ValidationError("archive index artifact count exceeds entry count")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "archive_id": self.archive_id,
            "packet_id": self.packet_id,
            "archive_address": self.archive_address,
            "packet_address": self.packet_address,
            "archive_byte_count": self.archive_byte_count,
            "payload_byte_count": self.payload_byte_count,
            "entry_count": self.entry_count,
            "artifact_count": self.artifact_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _entry_address(value: ModuleWorkbenchExecutionPacketArchiveIndexEntry) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-archive-index-entry")


def _make_entry(
    ordinal: int,
    archive: ModuleWorkbenchExecutionPacketArchive,
) -> ModuleWorkbenchExecutionPacketArchiveIndexEntry:
    body = {
        "ordinal": ordinal,
        "archive_id": archive.archive_id,
        "packet_id": archive.packet_id,
        "archive_address": archive.archive_address,
        "packet_address": archive.packet_address,
        "archive_byte_count": archive.archive_byte_count,
        "payload_byte_count": archive.payload_byte_count,
        "entry_count": archive.entry_count,
        "artifact_count": archive.artifact_count,
        "accepted": archive.accepted,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveIndexEntry(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveIndexEntry(
        **body,
        content_address=_entry_address(provisional),
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveIndex:
    """Addressed collection of archive records with duplicate and packet views."""

    index_id: str
    entries: tuple[ModuleWorkbenchExecutionPacketArchiveIndexEntry, ...]
    archive_count: int
    accepted_count: int
    rejected_count: int
    total_archive_byte_count: int
    total_payload_byte_count: int
    unique_archive_count: int
    duplicate_archive_count: int
    unique_packet_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _required_text(self.index_id, "index_id")
        if not self.entries or len(self.entries) > (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_ENTRIES
        ):
            raise ValidationError("archive index entries are incomplete or excessive")
        for field in (
            "archive_count",
            "accepted_count",
            "rejected_count",
            "total_archive_byte_count",
            "total_payload_byte_count",
            "unique_archive_count",
            "duplicate_archive_count",
            "unique_packet_count",
        ):
            _nonnegative(getattr(self, field), field)
        if self.archive_count != len(self.entries):
            raise ValidationError("archive index count does not conserve")
        if self.accepted_count + self.rejected_count != self.archive_count:
            raise ValidationError("archive index acceptance counts do not conserve")
        if self.accepted_count != sum(item.accepted for item in self.entries):
            raise ValidationError("archive index accepted count is inconsistent")
        if self.total_archive_byte_count != sum(item.archive_byte_count for item in self.entries):
            raise ValidationError("archive index archive bytes do not conserve")
        if self.total_payload_byte_count != sum(item.payload_byte_count for item in self.entries):
            raise ValidationError("archive index payload bytes do not conserve")
        archive_addresses = tuple(item.archive_address for item in self.entries)
        packet_addresses = tuple(item.packet_address for item in self.entries)
        if self.unique_archive_count != len(set(archive_addresses)):
            raise ValidationError("archive index unique archive count is inconsistent")
        if self.duplicate_archive_count != self.archive_count - self.unique_archive_count:
            raise ValidationError("archive index duplicate count is inconsistent")
        if self.unique_packet_count != len(set(packet_addresses)):
            raise ValidationError("archive index unique packet count is inconsistent")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.archive_count)):
            raise ValidationError("archive index ordinals must be contiguous")
        ids = tuple(item.archive_id for item in self.entries)
        if len(set(ids)) != len(ids):
            raise ValidationError("archive index archive IDs must be unique")
        if not isinstance(self.accepted, bool) or self.accepted != all(
            item.accepted for item in self.entries
        ):
            raise ValidationError("archive index acceptance is inconsistent")

    @property
    def duplicate_groups(self) -> dict[str, tuple[int, ...]]:
        groups: dict[str, list[int]] = {}
        for item in self.entries:
            groups.setdefault(item.archive_address, []).append(item.ordinal)
        return {
            address: tuple(ordinals)
            for address, ordinals in sorted(groups.items())
            if len(ordinals) > 1
        }

    @property
    def packet_groups(self) -> dict[str, tuple[int, ...]]:
        groups: dict[str, list[int]] = {}
        for item in self.entries:
            groups.setdefault(item.packet_address, []).append(item.ordinal)
        return {address: tuple(ordinals) for address, ordinals in sorted(groups.items())}

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_BOUNDARY,
            "index_id": self.index_id,
            "archive_count": self.archive_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "total_archive_byte_count": self.total_archive_byte_count,
            "total_payload_byte_count": self.total_payload_byte_count,
            "unique_archive_count": self.unique_archive_count,
            "duplicate_archive_count": self.duplicate_archive_count,
            "unique_packet_count": self.unique_packet_count,
            "duplicate_group_count": len(self.duplicate_groups),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def _index_address(value: ModuleWorkbenchExecutionPacketArchiveIndex) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-archive-index")


def build_module_workbench_execution_packet_archive_index(
    values: Iterable[ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path],
    *,
    index_id: str = "glio-noncode-module-workbench-execution-archive-index",
) -> ModuleWorkbenchExecutionPacketArchiveIndex:
    """Verify and index multiple archives without retaining binary payloads."""

    archives = tuple(_archive(value) for value in values)
    if not archives:
        raise ValidationError("archive index requires at least one archive")
    if len(archives) > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_ENTRIES:
        raise ValidationError("archive index exceeds the supported entry bound")
    entries = tuple(_make_entry(ordinal, archive) for ordinal, archive in enumerate(archives))
    body = {
        "index_id": index_id,
        "entries": entries,
        "archive_count": len(entries),
        "accepted_count": sum(item.accepted for item in entries),
        "rejected_count": sum(not item.accepted for item in entries),
        "total_archive_byte_count": sum(item.archive_byte_count for item in entries),
        "total_payload_byte_count": sum(item.payload_byte_count for item in entries),
        "unique_archive_count": len({item.archive_address for item in entries}),
        "duplicate_archive_count": len(entries) - len({item.archive_address for item in entries}),
        "unique_packet_count": len({item.packet_address for item in entries}),
        "accepted": all(item.accepted for item in entries),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveIndex(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveIndex(
        **body,
        content_address=_index_address(provisional),
    )


def verify_module_workbench_execution_packet_archive_index(
    value: ModuleWorkbenchExecutionPacketArchiveIndex,
) -> ModuleWorkbenchExecutionPacketArchiveIndex:
    """Verify index conservation and every nested entry address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveIndex):
        raise ValidationError("archive index verification requires a typed index")
    for entry in value.entries:
        if _entry_address(entry) != entry.content_address:
            raise ValidationError("archive index entry address mismatch")
    if _index_address(value) != value.content_address:
        raise ValidationError("archive index content address mismatch")
    return value


def _page(
    rows: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    text: str | None,
) -> tuple[list[dict[str, Any]], int]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_LIMIT:
        raise ValidationError("archive index query paging is invalid")
    filtered = rows
    if text:
        needle = text.casefold()
        filtered = [item for item in rows if needle in canonical_json(item).casefold()]
    return filtered[offset : offset + limit], len(filtered)


def query_module_workbench_execution_packet_archive_index(
    value: ModuleWorkbenchExecutionPacketArchiveIndex,
    *,
    resource: str = "archives",
    archive_id: str | None = None,
    packet_id: str | None = None,
    packet_address: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded archive, packet, duplicate, or summary index rows."""

    verify_module_workbench_execution_packet_archive_index(value)
    normalized = resource.casefold().strip()
    if normalized not in _RESOURCE_NAMES:
        raise ValidationError("unsupported archive index resource")
    if normalized == "summary":
        rows = [value.to_dict(include_entries=False)]
        index_used = "index_id"
    elif normalized == "duplicates":
        rows = [
            {
                "archive_address": address,
                "ordinals": list(ordinals),
                "duplicate_count": len(ordinals),
            }
            for address, ordinals in value.duplicate_groups.items()
        ]
        index_used = "archive_address"
    else:
        rows = [item.to_dict() for item in value.entries]
        if normalized == "packets":
            rows = [
                {
                    "packet_address": address,
                    "ordinals": list(ordinals),
                    "archive_count": len(ordinals),
                }
                for address, ordinals in value.packet_groups.items()
            ]
            index_used = "packet_address"
        else:
            if archive_id:
                rows = [item for item in rows if item.get("archive_id") == archive_id]
            if packet_id:
                rows = [item for item in rows if item.get("packet_id") == packet_id]
            if packet_address:
                rows = [item for item in rows if item.get("packet_address") == packet_address]
            if accepted is not None:
                rows = [item for item in rows if item.get("accepted") is accepted]
            index_used = "archive_id"
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    body = {
        "index_id": value.index_id,
        "index_address": value.content_address,
        "resource": normalized,
        "query": {
            "archive_id": archive_id,
            "packet_id": packet_id,
            "packet_address": packet_address,
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
            prefix="module-workbench-execution-packet-archive-index-query",
        )
    }


def resolve_module_workbench_execution_packet_archive_index_entry(
    value: ModuleWorkbenchExecutionPacketArchiveIndex,
    archive_address: str,
) -> ModuleWorkbenchExecutionPacketArchiveIndexEntry:
    """Resolve one archive address without exposing a source path."""

    verify_module_workbench_execution_packet_archive_index(value)
    matches = tuple(item for item in value.entries if item.archive_address == archive_address)
    if len(matches) != 1:
        raise ValidationError("archive index address is missing or ambiguous")
    return matches[0]


def module_workbench_execution_packet_archive_index_json(
    value: ModuleWorkbenchExecutionPacketArchiveIndex,
) -> str:
    """Return canonical JSON for an archive index."""

    verify_module_workbench_execution_packet_archive_index(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_index_csv(
    value: ModuleWorkbenchExecutionPacketArchiveIndex,
) -> str:
    """Return one deterministic CSV row per indexed archive."""

    verify_module_workbench_execution_packet_archive_index(value)
    fields = (
        "ordinal",
        "archive_id",
        "packet_id",
        "archive_address",
        "packet_address",
        "archive_byte_count",
        "payload_byte_count",
        "entry_count",
        "artifact_count",
        "accepted",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for entry in value.entries:
        writer.writerow(entry.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_index_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveIndex,
) -> str:
    """Render an index review with duplicate and packet rollups."""

    verify_module_workbench_execution_packet_archive_index(value)
    lines = [
        "# Module Workbench Execution Packet Archive Index",
        "",
        f"- Index: `{value.index_id}`",
        f"- Address: `{value.content_address}`",
        f"- Archives: `{value.archive_count}` (`{value.unique_archive_count}` unique, "
        f"`{value.duplicate_archive_count}` duplicates)",
        f"- Packets: `{value.unique_packet_count}`",
        f"- Bytes: `{value.total_archive_byte_count:,}` archive / "
        f"`{value.total_payload_byte_count:,}` payload",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "| Ordinal | Archive | Packet | Archive bytes | Entries | Accepted |",
        "|---:|---|---|---:|---:|---|",
    ]
    for entry in value.entries:
        lines.append(
            f"| {entry.ordinal} | `{entry.archive_address}` | `{entry.packet_address}` | "
            f"{entry.archive_byte_count:,} | {entry.entry_count} | "
            f"`{str(entry.accepted).lower()}` |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_index_schema() -> dict[str, Any]:
    """Describe the bounded, path-free archive index contract."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_BOUNDARY,
        "resources": list(_RESOURCE_NAMES),
        "filters": ["archive_id", "packet_id", "packet_address", "accepted", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_LIMIT,
        },
        "limits": {"max_entries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_ENTRIES},
        "inputs": ["typed_archives", "archive_bytes", "archive_paths"],
        "outputs": ["archive_catalog", "packet_groups", "duplicate_groups", "address_resolution"],
        "retains_binary_payloads": False,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_index_capabilities() -> dict[str, Any]:
    """Declare archive catalog, grouping, and resolution operations."""

    operations = (
        "index_verified_archives",
        "verify_nested_entry_addresses",
        "conserve_archive_counts",
        "conserve_archive_bytes",
        "conserve_payload_bytes",
        "count_unique_archives",
        "count_duplicate_archives",
        "group_archives_by_packet",
        "group_duplicate_archive_addresses",
        "resolve_archive_address",
        "query_archive_rows",
        "query_packet_groups",
        "query_duplicate_groups",
        "filter_archive_id",
        "filter_packet_id",
        "filter_packet_address",
        "filter_acceptance",
        "page_index_rows",
        "export_json",
        "export_csv",
        "export_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only": True,
        "deterministic": True,
        "path_free": True,
        "retains_binary_payloads": False,
        "identity_free": True,
    }


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_ENTRIES",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_INDEX_VERSION",
    "ModuleWorkbenchExecutionPacketArchiveIndex",
    "ModuleWorkbenchExecutionPacketArchiveIndexEntry",
    "build_module_workbench_execution_packet_archive_index",
    "module_workbench_execution_packet_archive_index_capabilities",
    "module_workbench_execution_packet_archive_index_csv",
    "module_workbench_execution_packet_archive_index_json",
    "module_workbench_execution_packet_archive_index_schema",
    "query_module_workbench_execution_packet_archive_index",
    "render_module_workbench_execution_packet_archive_index_markdown",
    "resolve_module_workbench_execution_packet_archive_index_entry",
    "verify_module_workbench_execution_packet_archive_index",
]
