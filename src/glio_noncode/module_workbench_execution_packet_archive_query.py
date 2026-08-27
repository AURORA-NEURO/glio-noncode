"""Chunk, resume, query, and reassemble packet archive transfers."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
    load_module_workbench_execution_packet_archive,
    verify_module_workbench_execution_packet_archive_value,
)
from .module_workbench_execution_packet_archive_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNK_SIZE,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT,
    ModuleWorkbenchExecutionPacketArchive,
    ModuleWorkbenchExecutionPacketArchiveChunk,
    ModuleWorkbenchExecutionPacketArchiveTransfer,
    ModuleWorkbenchExecutionPacketArchiveTransferState,
    address_module_workbench_execution_packet_archive_chunk,
    address_module_workbench_execution_packet_archive_transfer,
)
from .serialization import canonical_json, content_hash, hash_bytes


def _archive(
    value: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
) -> ModuleWorkbenchExecutionPacketArchive:
    if isinstance(value, ModuleWorkbenchExecutionPacketArchive):
        verify_module_workbench_execution_packet_archive_value(value)
        return value
    return build_module_workbench_execution_packet_archive(
        load_module_workbench_execution_packet_archive(value)
    )


def _chunk(
    archive: ModuleWorkbenchExecutionPacketArchive,
    ordinal: int,
    offset: int,
    payload: bytes,
) -> ModuleWorkbenchExecutionPacketArchiveChunk:
    body = {
        "archive_address": archive.archive_address,
        "ordinal": ordinal,
        "offset": offset,
        "byte_count": len(payload),
        "payload": payload,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveChunk(**body, content_address="pending")
    return ModuleWorkbenchExecutionPacketArchiveChunk(
        **body,
        content_address=address_module_workbench_execution_packet_archive_chunk(provisional),
    )


def chunk_module_workbench_execution_packet_archive(
    value: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
    *,
    chunk_size: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
) -> tuple[ModuleWorkbenchExecutionPacketArchiveChunk, ...]:
    """Split exact archive bytes into addressed, ordered chunks."""

    archive = _archive(value)
    if chunk_size < 1 or chunk_size > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNK_SIZE:
        raise ValidationError("archive chunk size is outside the supported bound")
    chunks = tuple(
        _chunk(archive, ordinal, offset, archive.archive_bytes[offset : offset + chunk_size])
        for ordinal, offset in enumerate(range(0, len(archive.archive_bytes), chunk_size))
    )
    if not chunks or len(chunks) > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNKS:
        raise ValidationError("archive chunk count is outside the supported bound")
    return chunks


def verify_module_workbench_execution_packet_archive_chunk(
    chunk: ModuleWorkbenchExecutionPacketArchiveChunk,
) -> ModuleWorkbenchExecutionPacketArchiveChunk:
    """Verify ordinal, byte range, payload address, and chunk address."""

    if not isinstance(chunk, ModuleWorkbenchExecutionPacketArchiveChunk):
        raise ValidationError("archive chunk verification requires a typed chunk")
    if address_module_workbench_execution_packet_archive_chunk(chunk) != chunk.content_address:
        raise ValidationError("archive chunk descriptor address mismatch")
    return chunk


def build_module_workbench_execution_packet_archive_transfer(
    value: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
    *,
    transfer_id: str = "glio-noncode-module-workbench-execution-transfer",
    chunk_size: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
    completed_chunks: Iterable[int] = (),
) -> ModuleWorkbenchExecutionPacketArchiveTransfer:
    """Create a resumable transfer receipt for one exact archive."""

    if not isinstance(transfer_id, str) or not transfer_id.strip():
        raise ValidationError("archive transfer ID is required")
    archive = _archive(value)
    chunks = chunk_module_workbench_execution_packet_archive(archive, chunk_size=chunk_size)
    ordinals = tuple(sorted(set(int(item) for item in completed_chunks)))
    if any(item < 0 or item >= len(chunks) for item in ordinals):
        raise ValidationError("completed archive chunk is outside the transfer")
    complete = len(ordinals) == len(chunks)
    state = (
        ModuleWorkbenchExecutionPacketArchiveTransferState.COMPLETED
        if complete
        else ModuleWorkbenchExecutionPacketArchiveTransferState.PARTIAL
        if ordinals
        else ModuleWorkbenchExecutionPacketArchiveTransferState.READY
    )
    body = {
        "transfer_id": transfer_id,
        "archive_id": archive.archive_id,
        "archive_address": archive.archive_address,
        "chunk_size": chunk_size,
        "total_byte_count": len(archive.archive_bytes),
        "total_chunks": len(chunks),
        "completed_chunks": ordinals,
        "state": state,
        "accepted": complete,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveTransfer(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveTransfer(
        **body,
        content_address=address_module_workbench_execution_packet_archive_transfer(provisional),
    )


def verify_module_workbench_execution_packet_archive_transfer(
    value: ModuleWorkbenchExecutionPacketArchiveTransfer,
) -> ModuleWorkbenchExecutionPacketArchiveTransfer:
    """Verify transfer state, bounds, and the transfer content address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveTransfer):
        raise ValidationError("archive transfer verification requires a typed transfer")
    if address_module_workbench_execution_packet_archive_transfer(value) != value.content_address:
        raise ValidationError("archive transfer address mismatch")
    return value


def assemble_module_workbench_execution_packet_archive_chunks(
    chunks: Iterable[ModuleWorkbenchExecutionPacketArchiveChunk],
    *,
    archive_address: str,
    total_byte_count: int,
) -> bytes:
    """Reassemble a complete chunk set and verify its binary archive address."""

    if not isinstance(archive_address, str) or not archive_address.strip():
        raise ValidationError("archive address is required for reassembly")
    if total_byte_count < 1:
        raise ValidationError("archive total byte count must be positive")
    selected = tuple(chunks)
    if not selected:
        raise ValidationError("archive reassembly requires chunks")
    for chunk in selected:
        verify_module_workbench_execution_packet_archive_chunk(chunk)
        if chunk.archive_address != archive_address:
            raise ValidationError("archive chunk belongs to a different archive")
    ordered = tuple(sorted(selected, key=lambda item: item.ordinal))
    if tuple(item.ordinal for item in ordered) != tuple(range(len(ordered))):
        raise ValidationError("archive chunk ordinals are incomplete")
    offset = 0
    for chunk in ordered:
        if chunk.offset != offset:
            raise ValidationError("archive chunk offsets are not contiguous")
        offset += chunk.byte_count
    if offset != total_byte_count:
        raise ValidationError("archive chunk bytes do not conserve")
    payload = b"".join(item.payload for item in ordered)
    if hash_bytes(payload, prefix="module-workbench-execution-packet-archive") != archive_address:
        raise ValidationError("reassembled archive address mismatch")
    return payload


def resume_module_workbench_execution_packet_archive_transfer(
    value: ModuleWorkbenchExecutionPacketArchiveTransfer,
    completed_chunks: Iterable[int],
) -> ModuleWorkbenchExecutionPacketArchiveTransfer:
    """Return a new transfer receipt with additional completed ordinals."""

    verify_module_workbench_execution_packet_archive_transfer(value)
    merged = tuple(sorted(set(value.completed_chunks) | {int(item) for item in completed_chunks}))
    if any(item < 0 or item >= value.total_chunks for item in merged):
        raise ValidationError("resumed archive chunk is outside the transfer")
    complete = len(merged) == value.total_chunks
    state = (
        ModuleWorkbenchExecutionPacketArchiveTransferState.COMPLETED
        if complete
        else ModuleWorkbenchExecutionPacketArchiveTransferState.PARTIAL
        if merged
        else ModuleWorkbenchExecutionPacketArchiveTransferState.READY
    )
    body = {
        "transfer_id": value.transfer_id,
        "archive_id": value.archive_id,
        "archive_address": value.archive_address,
        "chunk_size": value.chunk_size,
        "total_byte_count": value.total_byte_count,
        "total_chunks": value.total_chunks,
        "completed_chunks": merged,
        "state": state,
        "accepted": complete,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveTransfer(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveTransfer(
        **body,
        content_address=address_module_workbench_execution_packet_archive_transfer(provisional),
    )


def query_module_workbench_execution_packet_archive_chunks(
    value: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
    *,
    chunk_size: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
    ordinal: int | None = None,
    include_payloads: bool = False,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded chunk descriptors or binary payloads for a transfer."""

    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT:
        raise ValidationError("archive chunk query paging is invalid")
    chunks = chunk_module_workbench_execution_packet_archive(value, chunk_size=chunk_size)
    rows = [item.to_dict(include_payload=include_payloads) for item in chunks]
    if ordinal is not None:
        rows = [row for row in rows if row.get("ordinal") == ordinal]
    total = len(rows)
    archive = _archive(value)
    body = {
        "archive_id": archive.archive_id,
        "archive_address": archive.archive_address,
        "resource": "chunks",
        "query": {
            "chunk_size": chunk_size,
            "ordinal": ordinal,
            "include_payloads": include_payloads,
        },
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": "ordinal",
        "items": rows[offset : offset + limit],
        "accepted": True,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-archive-chunk-query",
        )
    }


def module_workbench_execution_packet_archive_transfer_json(
    value: ModuleWorkbenchExecutionPacketArchiveTransfer,
) -> str:
    """Return canonical transfer JSON."""

    verify_module_workbench_execution_packet_archive_transfer(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_chunks_csv(
    chunks: Iterable[ModuleWorkbenchExecutionPacketArchiveChunk],
) -> str:
    """Return one stable CSV row per chunk without binary payloads."""

    rows = tuple(chunks)
    for chunk in rows:
        verify_module_workbench_execution_packet_archive_chunk(chunk)
    fields = ("ordinal", "offset", "byte_count", "archive_address", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for chunk in rows:
        writer.writerow(chunk.to_dict())
    return output.getvalue()


def module_workbench_execution_packet_archive_transfer_schema() -> dict[str, Any]:
    """Describe chunking, transfer resumption, and reassembly guarantees."""

    return {
        "version": "module-workbench-execution-packet-archive-transfer-v1",
        "resources": ["chunks", "transfer", "reassembled_archive"],
        "transfer_states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveTransferState
        ],
        "chunk_limits": {
            "default_size": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
            "max_size": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNK_SIZE,
            "max_chunks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHUNKS,
        },
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT,
        },
        "inputs": ["typed_archive", "archive_bytes", "archive_path"],
        "outputs": ["addressed_chunks", "transfer_receipt", "reassembled_bytes"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_transfer_capabilities() -> dict[str, Any]:
    """Declare resumable transfer operations."""

    operations = (
        "chunk_archive",
        "address_chunk_bytes",
        "verify_chunk",
        "build_transfer",
        "resume_transfer",
        "verify_transfer",
        "query_chunks",
        "export_chunk_csv",
        "export_transfer_json",
        "reassemble_chunks",
        "verify_reassembled_archive",
        "enforce_chunk_bounds",
    )
    return {
        "version": "module-workbench-execution-packet-archive-transfer-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "offline": True,
        "resumable": True,
        "identity_free": True,
    }


__all__ = [
    "assemble_module_workbench_execution_packet_archive_chunks",
    "build_module_workbench_execution_packet_archive_transfer",
    "chunk_module_workbench_execution_packet_archive",
    "module_workbench_execution_packet_archive_chunks_csv",
    "module_workbench_execution_packet_archive_transfer_capabilities",
    "module_workbench_execution_packet_archive_transfer_json",
    "module_workbench_execution_packet_archive_transfer_schema",
    "query_module_workbench_execution_packet_archive_chunks",
    "resume_module_workbench_execution_packet_archive_transfer",
    "verify_module_workbench_execution_packet_archive_chunk",
    "verify_module_workbench_execution_packet_archive_transfer",
]
