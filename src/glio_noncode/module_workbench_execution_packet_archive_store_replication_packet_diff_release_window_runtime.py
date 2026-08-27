"""Ordered runtime handoff for release-window evaluation."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_batch import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_STAGE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_stage,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _stage(
    ordinal: int,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind,
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage:
    body = {
        "ordinal": ordinal,
        "kind": kind.value,
        "state": state.value,
        "artifact_address": artifact_address,
        "accepted": state
        != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.BLOCKED,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_STAGE_PREFIX
        + ":pending-stage",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_stage(
            provisional
        ),
    )


def _runtime(
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    stages: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage,
        ...,
    ],
    *,
    runtime_id: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime:
    body = {
        "window_id": window.window_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_BOUNDARY,
        "batch_address": window.batch_address,
        "policy_address": window.policy_address,
        "window_address": window.content_address,
        "stages": stages,
        "stage_count": len(stages),
        "completed_count": sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED.value
            for item in stages
        ),
        "skipped_count": sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.SKIPPED.value
            for item in stages
        ),
        "blocked_count": sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.BLOCKED.value
            for item in stages
        ),
        "accepted": all(item.accepted for item in stages),
        "state": window.state,
        "release_ready": window.release_ready,
        "detail": "release-window policy runtime completed",
    }
    # The contract uses window_id as the stable public runtime identifier.  A
    # caller-specific runtime ID is intentionally not serialized; accepting it
    # here only keeps the builder signature parallel with other runtimes.
    _text(runtime_id, "release-window runtime ID", 256)
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX
        + ":pending-runtime",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            provisional
        ),
    )


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
    batch: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy
    | None = None,
    *,
    window_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window"
    ),
    runtime_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-runtime"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime:
    """Execute load, verify, policy, audit, release, and closure stages."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(batch)
    window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        batch, policy, window_id=window_id
    )
    stages = [
        _stage(
            0,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind.LOAD,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED,
            batch.content_address,
            "packet-diff matrix is available for release-window evaluation",
        ),
        _stage(
            1,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind.VERIFY_MATRIX,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED,
            batch.content_address,
            "matrix items, counts, and content address are verified",
        ),
        _stage(
            2,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind.RESOLVE_POLICY,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED,
            window.policy_address,
            "release-window policy thresholds are resolved",
        ),
        _stage(
            3,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind.EVALUATE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED,
            window.content_address,
            "matrix counts and policy checks are evaluated",
        ),
        _stage(
            4,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind.AUDIT,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.BLOCKED
            if window.blocker_count
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED,
            window.content_address,
            "release-window checks are audited before promotion",
        ),
        _stage(
            5,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind.RELEASE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.SKIPPED
            if window.blocker_count
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED,
            window.content_address,
            "release readiness is retained without mutating packet stores",
        ),
        _stage(
            6,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind.COMPLETE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.SKIPPED
            if window.blocker_count
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED,
            window.content_address,
            "release-window runtime closure is recorded",
        ),
    ]
    return _runtime(window, tuple(stages), runtime_id=runtime_id)


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_from_directories(
    pairs: Sequence[tuple[str, str | Path, str | Path]],
    *,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy
    | None = None,
    batch_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch"
    ),
    window_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window"
    ),
    runtime_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-runtime"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime:
    """Run a release-window runtime directly from persisted packet pairs."""

    batch = build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories(
        pairs, batch_id=batch_id
    )
    return run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
        batch, policy, window_id=window_id, runtime_id=runtime_id
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime:
    """Verify stage addresses, order, and aggregate runtime address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
    ):
        raise ValidationError("release-window runtime verification requires a typed runtime")
    expected_kinds = tuple(
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind
    )
    if tuple(item.kind for item in value.stages) != expected_kinds:
        raise ValidationError("release-window runtime stage kinds are not ordered")
    for item in value.stages:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_stage(
                item
            )
            != item.content_address
        ):
            raise ValidationError("release-window runtime stage address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            value
        )
        != value.content_address
    ):
        raise ValidationError("release-window runtime address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
        value
    )
    output = io.StringIO(newline="")
    fields = ("ordinal", "kind", "state", "artifact_address", "accepted", "detail")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.stages:
        writer.writerow(item.to_dict())
    return output.getvalue()


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
    *,
    resource: str = "summary",
    kind: str | None = None,
    state: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded runtime summary or stage page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
        value
    )
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT
    ):
        raise ValidationError("release-window runtime query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "window_id"
    elif normalized == "stages":
        rows = [item.to_dict() for item in value.stages]
        if kind:
            rows = [row for row in rows if row["kind"] == kind]
        if state:
            rows = [row for row in rows if row["state"] == state]
        index_used = "kind"
    else:
        raise ValidationError("unsupported release-window runtime resource")
    body = {
        "resource": normalized,
        "query": {"kind": kind, "state": state},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify an addressed runtime query response."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("release-window runtime query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX
        + "-query",
    )
    if value["content_address"] != expected:
        raise ValidationError("release-window runtime query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "total",
        "offset",
        "limit",
        "index_used",
        "accepted",
        "reference_address",
        "content_address",
        "ordinal",
        "kind",
        "state",
        "artifact_address",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            writer.writerow(envelope | dict(row))
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Runtime",
        "",
        f"- window: `{value.window_id}`",
        f"- state: **{value.state}**",
        f"- release ready: `{str(value.release_ready).lower()}`",
        f"- stages: `{value.completed_count}/{value.stage_count}` completed; blocked: `{value.blocked_count}`; skipped: `{value.skipped_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | State | Accepted | Detail |",
        "|---:|---|---|---|---|",
    ]
    for item in value.stages:
        lines.append(
            f"| {item.ordinal} | {item.kind} | {item.state} | {str(item.accepted).lower()} | {item.detail} |"
        )
    return "\n".join(lines) + "\n"


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Runtime Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- reference: `{value.get('reference_address')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Kind | State | Accepted | Detail |",
        "|---:|---|---|---|---|",
    ]
    for row in value.get("items", []):
        lines.append(
            f"| {row.get('ordinal')} | {row.get('kind')} | {row.get('state')} | "
            f"{str(row.get('accepted')).lower()} | {row.get('detail')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_schema() -> (
    dict[str, Any]
):
    """Describe the seven-stage runtime."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_BOUNDARY,
        "stages": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind
        ],
        "stage_states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState
        ],
        "conservation": ["stage_order", "stage_counts", "acceptance", "window_address"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_capabilities() -> (
    dict[str, Any]
):
    """Declare runtime and stage-query operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION,
        "operations": ["run", "run_from_directories", "verify", "json", "csv", "markdown", "query"],
        "stages": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind
        ],
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_schema() -> (
    dict[str, Any]
):
    """Describe bounded runtime query filters."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX
        + "-query-v1",
        "resources": {"summary": ["summary"], "stages": ["stages"]},
        "filters": ["kind", "state"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
        },
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_capabilities() -> (
    dict[str, Any]
):
    """Declare runtime query exports."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX
        + "-query-v1",
        "operations": ["summary", "stages", "filter", "page", "json", "csv", "markdown", "verify"],
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime"
    )
]
