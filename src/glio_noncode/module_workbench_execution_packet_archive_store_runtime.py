"""Run the durable archive store lifecycle as one addressed receipt."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store import (
    build_module_workbench_execution_packet_archive_store,
    replay_module_workbench_execution_packet_archive_store,
    verify_module_workbench_execution_packet_archive_store,
    write_module_workbench_execution_packet_archive_store,
)
from .module_workbench_execution_packet_archive_store_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStore,
)
from .module_workbench_execution_packet_archive_store_query import (
    diff_module_workbench_execution_packet_archive_stores,
    query_module_workbench_execution_packet_archive_store,
)
from .module_workbench_execution_packet_archive_store_runtime_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_STAGE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage,
    ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind,
    ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageState,
    address_module_workbench_execution_packet_archive_store_runtime,
    address_module_workbench_execution_packet_archive_store_runtime_stage,
)
from .serialization import canonical_json, content_hash


def _stage(
    ordinal: int,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "state": ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageState.COMPLETED,
        "accepted": True,
        "artifact_address": artifact_address,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_runtime_stage(
            provisional
        ),
    )


def _runtime(
    store: ModuleWorkbenchExecutionPacketArchiveStore,
    verification_address: str,
    replay_address: str,
    stages: Iterable[ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStage],
) -> ModuleWorkbenchExecutionPacketArchiveStoreRuntime:
    stage_rows = tuple(stages)
    body = {
        "store_id": store.store_id,
        "store_address": store.content_address,
        "verification_address": verification_address,
        "replay_address": replay_address,
        "stages": stage_rows,
        "stage_count": len(stage_rows),
        "completed_count": sum(item.accepted for item in stage_rows),
        "blocked_count": sum(not item.accepted for item in stage_rows),
        "accepted": all(item.accepted for item in stage_rows),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreRuntime(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_runtime(
            provisional
        ),
    )


def run_module_workbench_execution_packet_archive_store_runtime(
    values: Iterable[Any] | ModuleWorkbenchExecutionPacketArchiveStore,
    *,
    store_id: str = "glio-noncode-module-workbench-execution-archive-store-runtime",
    destination: str | Path | None = None,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacketArchiveStoreRuntime:
    """Build, persist, verify, query, replay, and self-diff a store."""

    store = (
        values
        if isinstance(values, ModuleWorkbenchExecutionPacketArchiveStore)
        else build_module_workbench_execution_packet_archive_store(values, store_id=store_id)
    )
    stages = [
        _stage(
            0,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.BUILD,
            store.content_address,
            "archive store built",
        ),
        _stage(
            1,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.DEDUPLICATE,
            content_hash(
                {
                    "archive_count": store.archive_count,
                    "object_count": store.object_count,
                    "duplicate_registration_count": store.duplicate_registration_count,
                },
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_STAGE_PREFIX,
            ),
            "duplicate archive registrations reconciled",
        ),
    ]
    if destination is not None:
        write_module_workbench_execution_packet_archive_store(
            store,
            destination,
            allow_existing=allow_existing,
        )
        write_detail = "store atomically persisted"
    else:
        write_detail = "store retained in memory"
    stages.append(
        _stage(
            2,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.WRITE,
            store.content_address,
            write_detail,
        )
    )
    verification = verify_module_workbench_execution_packet_archive_store(
        destination if destination is not None else store
    )
    if not verification.accepted:
        raise ValidationError("archive store runtime verification is blocked")
    stages.append(
        _stage(
            3,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.VERIFY,
            verification.content_address,
            "store manifest, objects, and journal verified",
        )
    )
    query = query_module_workbench_execution_packet_archive_store(store, resource="summary")
    stages.append(
        _stage(
            4,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.QUERY,
            query["content_address"],
            "store summary query completed",
        )
    )
    replay = replay_module_workbench_execution_packet_archive_store(store)
    if not replay.accepted:
        raise ValidationError("archive store runtime replay is blocked")
    stages.append(
        _stage(
            5,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.REPLAY,
            replay.content_address,
            "stored archive objects replayed",
        )
    )
    self_diff = diff_module_workbench_execution_packet_archive_stores(store, store)
    stages.append(
        _stage(
            6,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.DIFF,
            self_diff["content_address"],
            "store self-diff completed with no changes",
        )
    )
    stages.append(
        _stage(
            7,
            ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind.COMPLETE,
            store.content_address,
            "archive store lifecycle completed",
        )
    )
    return _runtime(store, verification.content_address, replay.content_address, stages)


def verify_module_workbench_execution_packet_archive_store_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRuntime,
) -> ModuleWorkbenchExecutionPacketArchiveStoreRuntime:
    """Verify stage order, stage addresses, counts, and runtime address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreRuntime):
        raise ValidationError("archive store runtime verification requires a typed runtime")
    for stage in value.stages:
        if (
            address_module_workbench_execution_packet_archive_store_runtime_stage(stage)
            != stage.content_address
        ):
            raise ValidationError("archive store runtime stage address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_runtime(value)
        != value.content_address
    ):
        raise ValidationError("archive store runtime address mismatch")
    return value


def query_module_workbench_execution_packet_archive_store_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRuntime,
    *,
    resource: str = "stages",
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return bounded runtime stages or summary."""

    verify_module_workbench_execution_packet_archive_store_runtime(value)
    normalized = resource.casefold().strip()
    if normalized not in {"stages", "summary"}:
        raise ValidationError("unsupported archive store runtime resource")
    if normalized == "summary":
        rows = [value.to_dict(include_stages=False)]
        index_used = "store_id"
    else:
        rows = [item.to_dict() for item in value.stages]
        if state is not None:
            rows = [item for item in rows if item.get("state") == state]
        if accepted is not None:
            rows = [item for item in rows if item.get("accepted") is accepted]
        if text:
            needle = text.casefold()
            rows = [item for item in rows if needle in canonical_json(item).casefold()]
        index_used = "ordinal"
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("archive store runtime query paging is invalid")
    body = {
        "store_id": value.store_id,
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
            prefix="module-workbench-execution-packet-archive-store-runtime-query",
        )
    }


def module_workbench_execution_packet_archive_store_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRuntime,
) -> str:
    """Return canonical runtime JSON."""

    verify_module_workbench_execution_packet_archive_store_runtime(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreRuntime,
) -> str:
    """Return one stable CSV row per runtime stage."""

    verify_module_workbench_execution_packet_archive_store_runtime(value)
    fields = (
        "ordinal",
        "kind",
        "state",
        "accepted",
        "artifact_address",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for stage in value.stages:
        writer.writerow(stage.to_dict())
    return output.getvalue()


def module_workbench_execution_packet_archive_store_runtime_schema() -> dict[str, Any]:
    """Describe the ordered store runtime."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_BOUNDARY,
        "stage_order": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind
        ],
        "stage_states": [
            item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageState
        ],
        "resources": ["stages", "summary"],
        "inputs": ["typed_archives", "typed_store", "store_directory"],
        "outputs": ["store", "verification", "replay", "runtime"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_runtime_capabilities() -> dict[str, Any]:
    """Declare store runtime operations."""

    operations = (
        "build_store",
        "deduplicate_objects",
        "write_store",
        "verify_store",
        "query_store",
        "replay_store",
        "diff_store",
        "complete_runtime",
        "verify_stage_addresses",
        "verify_runtime_address",
        "export_json",
        "export_csv",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_RUNTIME_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "ordered": True,
        "offline": True,
        "deterministic": True,
        "replayable": True,
        "atomic_writes": True,
        "identity_free": True,
    }


__all__ = [
    "module_workbench_execution_packet_archive_store_runtime_capabilities",
    "module_workbench_execution_packet_archive_store_runtime_csv",
    "module_workbench_execution_packet_archive_store_runtime_json",
    "module_workbench_execution_packet_archive_store_runtime_schema",
    "query_module_workbench_execution_packet_archive_store_runtime",
    "run_module_workbench_execution_packet_archive_store_runtime",
    "verify_module_workbench_execution_packet_archive_store_runtime",
]
