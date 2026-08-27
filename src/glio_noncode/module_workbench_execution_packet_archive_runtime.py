"""Run the complete archive transport lifecycle as an addressed runtime."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
    load_module_workbench_execution_packet_archive,
    unpack_module_workbench_execution_packet_archive,
    verify_module_workbench_execution_packet_archive,
    write_module_workbench_execution_packet_archive,
)
from .module_workbench_execution_packet_archive_contracts import (
    ModuleWorkbenchExecutionPacketArchive,
)
from .module_workbench_execution_packet_archive_query import (
    assemble_module_workbench_execution_packet_archive_chunks,
    build_module_workbench_execution_packet_archive_transfer,
    chunk_module_workbench_execution_packet_archive,
    query_module_workbench_execution_packet_archive_chunks,
    resume_module_workbench_execution_packet_archive_transfer,
)
from .module_workbench_execution_packet_archive_runtime_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_VERSION,
    ModuleWorkbenchExecutionPacketArchiveRuntime,
    ModuleWorkbenchExecutionPacketArchiveRuntimeStage,
    ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind,
    ModuleWorkbenchExecutionPacketArchiveRuntimeStageState,
    address_module_workbench_execution_packet_archive_runtime,
    address_module_workbench_execution_packet_archive_runtime_stage,
)
from .module_workbench_execution_packet_contracts import ModuleWorkbenchExecutionPacket
from .serialization import canonical_json, content_hash, hash_bytes


def _stage(
    kind: ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind,
    accepted: bool,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveRuntimeStage:
    body = {
        "kind": kind,
        "state": (
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageState.COMPLETED
            if accepted
            else ModuleWorkbenchExecutionPacketArchiveRuntimeStageState.BLOCKED
        ),
        "accepted": accepted,
        "artifact_address": artifact_address,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveRuntimeStage(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_runtime_stage(
            provisional
        ),
    )


def _runtime(
    archive: ModuleWorkbenchExecutionPacketArchive,
    verification_address: str,
    transfer_address: str,
    reassembled_address: str,
    stages: tuple[ModuleWorkbenchExecutionPacketArchiveRuntimeStage, ...],
) -> ModuleWorkbenchExecutionPacketArchiveRuntime:
    body = {
        "archive_id": archive.archive_id,
        "archive_address": archive.archive_address,
        "verification_address": verification_address,
        "transfer_address": transfer_address,
        "reassembled_address": reassembled_address,
        "stages": stages,
        "stage_count": len(stages),
        "completed_count": sum(item.accepted for item in stages),
        "blocked_count": sum(not item.accepted for item in stages),
        "accepted": all(item.accepted for item in stages),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveRuntime(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_runtime(provisional),
    )


def run_module_workbench_execution_packet_archive_runtime(
    value: ModuleWorkbenchExecutionPacket | ModuleWorkbenchExecutionPacketArchive | str | Path,
    *,
    destination: str | Path | None = None,
    unpack_destination: str | Path | None = None,
    chunk_size: int = 65536,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacketArchiveRuntime:
    """Build, persist, verify, chunk, resume, reassemble, unpack, and query an archive."""

    archive = (
        value
        if isinstance(value, ModuleWorkbenchExecutionPacketArchive)
        else build_module_workbench_execution_packet_archive(value)
    )
    stages: list[ModuleWorkbenchExecutionPacketArchiveRuntimeStage] = [
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.BUILD,
            True,
            archive.archive_address,
            f"built {archive.entry_count} deterministic archive entries",
        )
    ]
    if destination is None:
        stages.append(
            _stage(
                ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.WRITE,
                True,
                archive.archive_address,
                "retained archive bytes in memory; no file destination requested",
            )
        )
        verification = verify_module_workbench_execution_packet_archive(archive.archive_bytes)
    else:
        write_module_workbench_execution_packet_archive(
            archive,
            destination,
            allow_existing=allow_existing,
        )
        stages.append(
            _stage(
                ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.WRITE,
                True,
                archive.archive_address,
                "wrote exact ZIP bytes with atomic replacement",
            )
        )
        verification = verify_module_workbench_execution_packet_archive(destination)
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.VERIFY,
            verification.accepted,
            verification.content_address,
            "verified ZIP structure, paths, manifest, bytes, packet links, and public fields",
        )
    )
    loaded = load_module_workbench_execution_packet_archive(archive.archive_bytes)
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.LOAD,
            loaded.content_address == archive.packet_address,
            loaded.content_address,
            "restored the addressed packet without source access",
        )
    )
    chunks = chunk_module_workbench_execution_packet_archive(
        archive,
        chunk_size=chunk_size,
    )
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.CHUNK,
            bool(chunks),
            chunks[0].content_address,
            f"addressed {len(chunks)} ordered byte chunks",
        )
    )
    transfer = build_module_workbench_execution_packet_archive_transfer(
        archive,
        chunk_size=chunk_size,
        completed_chunks=(0,) if len(chunks) > 1 else tuple(range(len(chunks))),
    )
    resumed = resume_module_workbench_execution_packet_archive_transfer(
        transfer,
        range(1, len(chunks)),
    )
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.RESUME,
            resumed.accepted,
            resumed.content_address,
            f"resumed transfer to {len(resumed.completed_chunks)}/{resumed.total_chunks} chunks",
        )
    )
    reassembled = assemble_module_workbench_execution_packet_archive_chunks(
        chunks,
        archive_address=archive.archive_address,
        total_byte_count=archive.archive_byte_count,
    )
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.ASSEMBLE,
            reassembled == archive.archive_bytes,
            hash_bytes(reassembled, prefix="module-workbench-execution-packet-archive"),
            "reassembled chunks match the original archive address",
        )
    )
    if unpack_destination is None:
        unpacked_ok = True
        unpack_detail = "unpack validated in memory; no directory destination requested"
    else:
        unpack_module_workbench_execution_packet_archive(
            archive.archive_bytes,
            unpack_destination,
            allow_existing=allow_existing,
        )
        unpacked_ok = True
        unpack_detail = "verified and atomically unpacked archive members"
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.UNPACK,
            unpacked_ok,
            archive.packet_address,
            unpack_detail,
        )
    )
    query = query_module_workbench_execution_packet_archive_chunks(
        archive,
        chunk_size=chunk_size,
        limit=1,
    )
    stages.append(
        _stage(
            ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind.QUERY,
            bool(query.get("accepted")),
            str(query["content_address"]),
            "queried the bounded chunk resource",
        )
    )
    return _runtime(
        archive,
        verification.content_address,
        resumed.content_address,
        hash_bytes(reassembled, prefix="module-workbench-execution-packet-archive"),
        tuple(stages),
    )


def verify_module_workbench_execution_packet_archive_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveRuntime,
) -> ModuleWorkbenchExecutionPacketArchiveRuntime:
    """Verify every stage address and the whole runtime address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveRuntime):
        raise ValidationError("archive runtime verification requires a typed runtime")
    for stage in value.stages:
        if (
            address_module_workbench_execution_packet_archive_runtime_stage(stage)
            != stage.content_address
        ):
            raise ValidationError(f"archive runtime stage address mismatch: {stage.kind.value}")
    if (
        address_module_workbench_execution_packet_archive_runtime(value)
        != value.content_address
    ):
        raise ValidationError("archive runtime address mismatch")
    return value


def query_module_workbench_execution_packet_archive_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveRuntime,
    *,
    resource: str = "stages",
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return bounded runtime stages or one summary row."""

    verify_module_workbench_execution_packet_archive_runtime(value)
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("archive runtime query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "stages":
        rows = [item.to_dict() for item in value.stages]
        index_used = "kind"
    elif normalized == "summary":
        rows = [value.to_dict(include_stages=False)]
        index_used = "archive_id"
    else:
        raise ValidationError("archive runtime resource must be stages or summary")
    if state:
        rows = [row for row in rows if row.get("state") == state]
    if accepted is not None:
        rows = [row for row in rows if row.get("accepted") is accepted]
    if text:
        rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
    body = {
        "archive_id": value.archive_id,
        "runtime_address": value.content_address,
        "resource": normalized,
        "query": {"state": state, "accepted": accepted, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-archive-runtime-query",
        )
    }


def module_workbench_execution_packet_archive_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveRuntime,
) -> str:
    """Return canonical archive runtime JSON."""

    verify_module_workbench_execution_packet_archive_runtime(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveRuntime,
) -> str:
    """Return one stable CSV row per runtime stage."""

    verify_module_workbench_execution_packet_archive_runtime(value)
    fields = ("kind", "state", "accepted", "artifact_address", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for stage in value.stages:
        writer.writerow(stage.to_dict())
    return output.getvalue()


def module_workbench_execution_packet_archive_runtime_schema() -> dict[str, Any]:
    """Describe the ordered archive transport runtime."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_BOUNDARY,
        "stage_order": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind
        ],
        "stage_states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveRuntimeStageState
        ],
        "resources": ["stages", "summary"],
        "inputs": ["typed_packet", "typed_archive", "archive_path"],
        "outputs": ["runtime", "archive", "packet_directory"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_runtime_capabilities() -> dict[str, Any]:
    """Declare archive runtime operations."""

    operations = (
        "build_archive",
        "write_archive",
        "verify_archive",
        "load_packet",
        "chunk_archive",
        "resume_transfer",
        "assemble_archive",
        "unpack_archive",
        "query_chunks",
        "query_stages",
        "export_json",
        "export_csv",
        "verify_stage_addresses",
        "verify_runtime_address",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_RUNTIME_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "ordered": True,
        "deterministic": True,
        "offline": True,
        "resumable": True,
        "identity_free": True,
    }


__all__ = [
    "module_workbench_execution_packet_archive_runtime_capabilities",
    "module_workbench_execution_packet_archive_runtime_csv",
    "module_workbench_execution_packet_archive_runtime_json",
    "module_workbench_execution_packet_archive_runtime_schema",
    "query_module_workbench_execution_packet_archive_runtime",
    "run_module_workbench_execution_packet_archive_runtime",
    "verify_module_workbench_execution_packet_archive_runtime",
]
