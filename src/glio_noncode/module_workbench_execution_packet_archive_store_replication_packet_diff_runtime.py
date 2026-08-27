"""Run packet diff and release evaluation as an ordered addressed runtime."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_inputs,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_STAGE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_stage,
)
from .serialization import canonical_json, content_hash


def _stage(
    ordinal: int,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind,
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage:
    accepted = state is not (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.BLOCKED
    )
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "state": state,
        "artifact_address": artifact_address,
        "accepted": accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_STAGE_PREFIX
        + ":pending-stage",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_stage(
            provisional
        ),
    )


def _runtime(
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    release: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
    stages: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage, ...],
    *,
    diff_id: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime:
    body = {
        "diff_id": diff_id,
        "version": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_VERSION
        ),
        "boundary": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_BOUNDARY
        ),
        "left_packet_address": diff.left_packet_address,
        "right_packet_address": diff.right_packet_address,
        "diff_address": diff.content_address,
        "release_address": release.content_address,
        "stages": stages,
        "stage_count": len(stages),
        "completed_count": sum(
            item.state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED
            )
            for item in stages
        ),
        "skipped_count": sum(
            item.state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.SKIPPED
            )
            for item in stages
        ),
        "blocked_count": sum(
            item.state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.BLOCKED
            )
            for item in stages
        ),
        "accepted": all(item.accepted for item in stages),
        "detail": "packet diff and release evaluation completed",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_PREFIX
        + ":pending-runtime",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
            provisional
        ),
    )


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket | str | Path,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket | str | Path,
    *,
    diff_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-runtime"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime:
    """Load, verify, compare, release-gate, and close a packet diff runtime."""

    if isinstance(left, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket) and isinstance(
        right, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket
    ):
        left_packet = left
        right_packet = right
    elif not isinstance(
        left, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket
    ) and not isinstance(right, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket):
        diff = load_module_workbench_execution_packet_archive_store_replication_packet_diff_inputs(
            left, right, diff_id=diff_id
        )
        left_packet = None
        right_packet = None
    else:
        raise ValidationError("diff runtime inputs must both be typed or both be directories")
    if left_packet is not None and right_packet is not None:
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            left_packet, right_packet, diff_id=diff_id
        )
    release = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
        diff
    )
    source_left = diff.left_packet_address
    source_right = diff.right_packet_address
    stages = (
        _stage(
            0,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind.LOAD,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED,
            source_left,
            "left and right packet inputs are available",
        ),
        _stage(
            1,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind.VERIFY_LEFT,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED,
            source_left,
            "left packet boundary is verified before comparison",
        ),
        _stage(
            2,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind.VERIFY_RIGHT,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED,
            source_right,
            "right packet boundary is verified before comparison",
        ),
        _stage(
            3,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind.COMPARE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED,
            diff.content_address,
            "artifact and check actions are classified",
        ),
        _stage(
            4,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind.RELEASE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED,
            release.content_address,
            "candidate release state is derived from diff checks",
        ),
        _stage(
            5,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind.COMPLETE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED,
            release.content_address,
            "diff runtime lifecycle is closed",
        ),
    )
    return _runtime(diff, release, stages, diff_id=diff_id)


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime:
    """Verify runtime stage addresses and aggregate address."""

    if not isinstance(
        value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime
    ):
        raise ValidationError("diff runtime verification requires a typed runtime")
    for item in value.stages:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_stage(
                item
            )
            != item.content_address
        ):
            raise ValidationError("diff runtime stage address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
            value
        )
        != value.content_address
    ):
        raise ValidationError("diff runtime address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(value)
    output = io.StringIO(newline="")
    fields = ("ordinal", "kind", "state", "artifact_address", "accepted", "detail")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.stages:
        writer.writerow(item.to_dict())
    return output.getvalue()


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
    *,
    resource: str = "summary",
    kind: str | None = None,
    state: str | None = None,
    offset: int = 0,
    limit: int = (
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_DEFAULT_LIMIT
    ),
) -> dict[str, Any]:
    """Return a bounded runtime summary or stage page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(value)
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT
    ):
        raise ValidationError("diff runtime query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "diff_id"
    elif normalized == "stages":
        rows = [item.to_dict() for item in value.stages]
        if kind:
            rows = [item for item in rows if item.get("kind") == kind]
        if state:
            rows = [item for item in rows if item.get("state") == state]
        index_used = "kind"
    else:
        raise ValidationError("unsupported diff runtime resource")
    items = rows[offset : offset + limit]
    body = {
        "resource": normalized,
        "query": {"kind": kind, "state": state},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": items,
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_PREFIX
            + "-query",
        )
    }
