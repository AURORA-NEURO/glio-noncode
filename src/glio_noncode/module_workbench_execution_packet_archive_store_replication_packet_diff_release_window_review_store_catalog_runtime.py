"""Execute and inspect the deterministic catalog runtime.

The runtime makes collection-level readiness explicit.  It does not approve
or modify a member review store.  It loads the catalog, verifies its address,
conserves entries and journal operations, reconciles release windows, resolves
the selected collection, and only then closes readiness.  Empty, held, or
blocked catalogs stop at the first unsafe stage and retain skipped stages.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_STAGE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_stage,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _bounded(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _stage(
    ordinal: int,
    *,
    kind: str,
    state: str,
    input_address: str | None,
    output_address: str | None,
    accepted: bool,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "accepted": accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage(
        **body, content_address="pending:stage"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_stage(
            provisional
        ),
    )


def _stage_output(kind: str, payload: Any) -> str:
    return content_hash(
        {"kind": kind, "payload": payload},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_STAGE_PREFIX
        + "-output",
    )


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    *,
    runtime_id: str = "glio-noncode-review-store-catalog-runtime",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime:
    """Run eight ordered catalog stages with fail-closed readiness."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ):
        raise ValidationError("catalog runtime requires a typed catalog")
    runtime_id = _text(runtime_id, "catalog runtime ID", 256)
    stages: list[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage
    ] = []
    stages.append(
        _stage(
            0,
            kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.LOAD.value,
            state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
            input_address=None,
            output_address=value.content_address,
            accepted=True,
            detail="loaded one addressed review-store catalog",
        )
    )
    catalog_verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    if not catalog_verification.accepted:
        stages.append(
            _stage(
                1,
                kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.VERIFY_CATALOG.value,
                state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.BLOCKED.value,
                input_address=value.content_address,
                output_address=catalog_verification.content_address,
                accepted=False,
                detail="catalog verification did not pass",
            )
        )
        for ordinal, kind in enumerate(
            (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.VERIFY_ENTRIES.value,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.VERIFY_OPERATIONS.value,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.RECONCILE_WINDOWS.value,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.RESOLVE_RELEASE_SET.value,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.EVALUATE_READINESS.value,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.COMPLETE.value,
            ),
            start=2,
        ):
            stages.append(
                _stage(
                    ordinal,
                    kind=kind,
                    state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.SKIPPED.value,
                    input_address=None,
                    output_address=None,
                    accepted=False,
                    detail="stage skipped after a failed catalog verification",
                )
            )
    else:
        entries_output = _stage_output("entries", [item.to_dict() for item in value.entries])
        stages.append(
            _stage(
                1,
                kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.VERIFY_CATALOG.value,
                state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
                input_address=value.content_address,
                output_address=catalog_verification.content_address,
                accepted=True,
                detail="catalog content and independent checks passed",
            )
        )
        stages.append(
            _stage(
                2,
                kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.VERIFY_ENTRIES.value,
                state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
                input_address=catalog_verification.content_address,
                output_address=entries_output,
                accepted=True,
                detail="all member entry addresses and ordinals are conserved",
            )
        )
        operations_output = _stage_output(
            "operations", [item.to_dict() for item in value.operations]
        )
        stages.append(
            _stage(
                3,
                kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.VERIFY_OPERATIONS.value,
                state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
                input_address=entries_output,
                output_address=operations_output,
                accepted=True,
                detail="genesis and registration operation chain is conserved",
            )
        )
        windows = tuple(sorted({item.window_address for item in value.entries}))
        windows_output = _stage_output("windows", windows)
        stages.append(
            _stage(
                4,
                kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.RECONCILE_WINDOWS.value,
                state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
                input_address=operations_output,
                output_address=windows_output,
                accepted=True,
                detail=f"reconciled {len(windows)} distinct evidence window address(es)",
            )
        )
        release_set_output = _stage_output(
            "release-set", tuple(item.store_id for item in value.entries)
        )
        stages.append(
            _stage(
                5,
                kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.RESOLVE_RELEASE_SET.value,
                state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
                input_address=windows_output,
                output_address=release_set_output,
                accepted=True,
                detail="resolved the bounded catalog member set",
            )
        )
        readiness_input = release_set_output
        if value.release_ready:
            stages.append(
                _stage(
                    6,
                    kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.EVALUATE_READINESS.value,
                    state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
                    input_address=readiness_input,
                    output_address=_stage_output("readiness", value.release_ready),
                    accepted=True,
                    detail="all catalog members are release-ready",
                )
            )
            stages.append(
                _stage(
                    7,
                    kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.COMPLETE.value,
                    state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value,
                    input_address=stages[-1].content_address,
                    output_address=_stage_output("complete", value.content_address),
                    accepted=True,
                    detail="catalog runtime closed successfully",
                )
            )
        else:
            stages.append(
                _stage(
                    6,
                    kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.EVALUATE_READINESS.value,
                    state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.BLOCKED.value,
                    input_address=readiness_input,
                    output_address=None,
                    accepted=False,
                    detail="catalog contains held or non-release-ready members",
                )
            )
            stages.append(
                _stage(
                    7,
                    kind=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind.COMPLETE.value,
                    state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.SKIPPED.value,
                    input_address=None,
                    output_address=None,
                    accepted=False,
                    detail="completion is withheld until catalog readiness is repaired",
                )
            )
    state = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeState.COMPLETED.value
        if len(stages) == 8 and all(item.state == "completed" for item in stages)
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeState.BLOCKED.value
    )
    body = {
        "catalog_id": value.catalog_id,
        "catalog_address": value.content_address,
        "state": state,
        "release_ready": value.release_ready and state == "completed",
        "accepted": state == "completed",
        "stages": tuple(stages),
        "completed_count": sum(item.state == "completed" for item in stages),
        "blocked_count": sum(item.state == "blocked" for item in stages),
        "skipped_count": sum(item.state == "skipped" for item in stages),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime(
        **body, content_address="pending:runtime"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            provisional
        ),
    )


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_from_directory(
    directory: str | Path,
    *,
    runtime_id: str = "glio-noncode-review-store-catalog-runtime",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime:
    return run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            directory
        ),
        runtime_id=runtime_id,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
) -> bool:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
    ):
        raise ValidationError("catalog runtime verification requires a typed runtime")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            value
        )
        != value.content_address
    ):
        raise ValidationError("catalog runtime content address mismatch")
    return True


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "kind",
        "state",
        "input_address",
        "output_address",
        "accepted",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for stage in value.stages:
        writer.writerow(stage.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        value
    )
    lines = [
        "# Review-Store Catalog Runtime",
        "",
        f"- state: `{value.state}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- completed: `{value.completed_count}`",
        f"- blocked: `{value.blocked_count}`",
        f"- skipped: `{value.skipped_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Stage | State | Accepted | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {stage.ordinal} | `{stage.kind}` | `{stage.state}` | `{str(stage.accepted).lower()}` | {stage.detail} |"
        for stage in value.stages
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
    *,
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        value
    )
    offset = _bounded(offset, "catalog runtime query offset", 1000000)
    limit = _bounded(limit, "catalog runtime query limit", 512)
    if limit == 0:
        raise ValidationError("catalog runtime query limit must be positive")
    if state is not None:
        state = _text(state, "catalog runtime query state", 64)
    if text is not None:
        text = _text(text, "catalog runtime query text", 4096).casefold()
    rows = [item.to_dict() for item in value.stages]
    if state is not None:
        rows = [row for row in rows if row["state"] == state]
    if accepted is not None:
        rows = [row for row in rows if row["accepted"] == accepted]
    if text is not None:
        rows = [
            row for row in rows if text in " ".join(str(item) for item in row.values()).casefold()
        ]
    page = rows[offset : offset + limit]
    payload = {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_PREFIX
        + "-query",
        "catalog_id": value.catalog_id,
        "runtime_address": value.content_address,
        "resource": "stages",
        "offset": offset,
        "limit": limit,
        "total": len(rows),
        "returned": len(page),
        "accepted": True,
        "rows": page,
    }
    payload["query_address"] = content_hash(
        payload,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_PREFIX
        + "-query",
    )
    return payload


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query(
    payload: Mapping[str, Any],
) -> bool:
    if (
        not isinstance(payload, Mapping)
        or not payload.get("accepted")
        or not isinstance(payload.get("query_address"), str)
    ):
        return False
    body = dict(payload)
    address = body.pop("query_address")
    return address == content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_PREFIX
        + "-query",
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_json(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query(
        payload
    ):
        raise ValidationError("catalog runtime query receipt is invalid")
    return canonical_json(dict(payload)) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_csv(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query(
        payload
    ):
        raise ValidationError("catalog runtime query receipt is invalid")
    output = io.StringIO(newline="")
    fields = ("ordinal", "kind", "state", "accepted", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in payload.get("rows", ()):
        writer.writerow({field: row.get(field) for field in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_markdown(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query(
        payload
    ):
        raise ValidationError("catalog runtime query receipt is invalid")
    lines = [
        "# Review-Store Catalog Runtime Query",
        "",
        f"- returned: `{payload.get('returned')}` of `{payload.get('total')}`",
        f"- query address: `{payload.get('query_address')}`",
        "",
        "| # | Stage | State | Accepted | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | `{row.get('kind', '')}` | `{row.get('state', '')}` | `{str(row.get('accepted', '')).lower()}` | {row.get('detail', '')} |"
        for row in payload.get("rows", ())
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "runtime_states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeState
        ],
        "stage_kinds": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind
        ],
        "stage_states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState
        ],
        "stage_count": 8,
        "limits": {
            "limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": [
            "run",
            "load",
            "verify",
            "query",
            "json",
            "csv",
            "markdown",
            "schema",
            "capabilities",
        ],
        "guarantees": [
            "eight ordered stages",
            "fail-closed readiness",
            "addressed stage receipts",
            "bounded stage queries",
            "deterministic output",
            "identity-free output",
        ],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "resource": "stages",
        "filters": ["state", "accepted", "text", "offset", "limit"],
        "limits": {
            "limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": ["query", "filter", "paginate", "verify", "json", "csv", "markdown"],
        "guarantees": [
            "bounded results",
            "addressed query receipt",
            "deterministic order",
            "identity-free output",
        ],
    }
