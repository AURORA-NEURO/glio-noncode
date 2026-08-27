"""Run a fail-closed runtime over a release-window review ledger."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_from_directories,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_from_directories,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_STAGE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_stage,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _stage(
    ordinal: int,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind,
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState,
    input_address: str | None,
    output_address: str | None,
    accepted: bool,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage:
    body = {
        "ordinal": ordinal,
        "stage_id": f"release-window-review-runtime-{ordinal}-{kind.value}",
        "kind": kind.value,
        "state": state.value,
        "input_address": input_address,
        "output_address": output_address,
        "accepted": accepted,
        "detail": _text(detail, "review runtime stage detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_STAGE_PREFIX
        + ":pending-stage",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_stage(
            provisional
        ),
    )


def _runtime(
    ledger: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    assurance: Any,
    *,
    runtime_id: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime:
    """Build the seven ordered stages and conserve their outcome counts."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        ledger, window=window, assurance=assurance
    )
    stages: list[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage
    ] = []
    load = _stage(
        0,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.LOAD,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED,
        None,
        ledger.content_address,
        True,
        "review ledger loaded as an immutable input",
    )
    stages.append(load)
    window_stage = _stage(
        1,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.VERIFY_WINDOW,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED,
        load.content_address,
        window.content_address,
        True,
        "release-window evidence verified and linked",
    )
    stages.append(window_stage)
    assurance_stage = _stage(
        2,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.VERIFY_ASSURANCE,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED,
        window_stage.content_address,
        assurance.content_address,
        True,
        "independent assurance evidence verified and linked",
    )
    stages.append(assurance_stage)
    ledger_stage = _stage(
        3,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.VERIFY_LEDGER,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED
        if ledger.accepted
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.BLOCKED,
        assurance_stage.content_address,
        ledger.content_address,
        ledger.accepted,
        "review entry chain and content addresses verified"
        if ledger.accepted
        else "review ledger has no accepted decision chain",
    )
    stages.append(ledger_stage)
    if ledger.head_address is None:
        head_stage = _stage(
            4,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.RESOLVE_HEAD,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.BLOCKED,
            ledger_stage.content_address,
            None,
            False,
            "no explicit review decision exists; handoff is blocked",
        )
        stages.append(head_stage)
        stages.append(
            _stage(
                5,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.EVALUATE_HANDOFF,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.SKIPPED,
                head_stage.content_address,
                None,
                True,
                "handoff evaluation skipped after missing-head blocker",
            )
        )
        stages.append(
            _stage(
                6,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.COMPLETE,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.SKIPPED,
                stages[-1].content_address,
                None,
                True,
                "runtime closure skipped after missing-head blocker",
            )
        )
    else:
        head_stage = _stage(
            4,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.RESOLVE_HEAD,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED,
            ledger_stage.content_address,
            ledger.head_address,
            True,
            "latest review decision resolved from the append-only head",
        )
        stages.append(head_stage)
        handoff_ready = ledger.release_ready and window.release_ready and assurance.release_ready
        handoff_detail = (
            "promote decision is admissible because window and assurance are release-ready"
            if handoff_ready
            else "review decision is complete but release handoff remains held"
        )
        handoff_stage = _stage(
            5,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.EVALUATE_HANDOFF,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED,
            head_stage.content_address,
            ledger.head_address,
            True,
            handoff_detail,
        )
        stages.append(handoff_stage)
        stages.append(
            _stage(
                6,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind.COMPLETE,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED,
                handoff_stage.content_address,
                ledger.content_address,
                True,
                "review runtime completed without mutating the evidence store",
            )
        )
    body = {
        "runtime_id": _text(runtime_id, "review runtime ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_BOUNDARY,
        "ledger_address": ledger.content_address,
        "window_address": window.content_address,
        "assurance_address": assurance.content_address,
        "stages": tuple(stages),
        "stage_count": len(stages),
        "completed_count": sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED.value
            for item in stages
        ),
        "blocked_count": sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.BLOCKED.value
            for item in stages
        ),
        "skipped_count": sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.SKIPPED.value
            for item in stages
        ),
        "state": "completed"
        if not any(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.BLOCKED.value
            for item in stages
        )
        else "blocked",
        "release_ready": bool(
            ledger.release_ready
            and window.release_ready
            and assurance.release_ready
            and ledger.head_address
        ),
        "accepted": not any(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.BLOCKED.value
            for item in stages
        ),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX
        + ":pending-runtime",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            provisional
        ),
    )


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
    ledger: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    assurance: Any,
    *,
    runtime_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-runtime",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime:
    """Run the review runtime on typed evidence."""

    return _runtime(ledger, window, assurance, runtime_id=runtime_id)


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_from_directories(
    pairs: Sequence[tuple[str, str | Path, str | Path]],
    *,
    decisions: Sequence[Mapping[str, Any]] = (),
    policy: Any | None = None,
    batch_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch",
    window_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window",
    ledger_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review",
    runtime_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-runtime",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime:
    """Build all review evidence from persisted directories and run it."""

    ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_from_directories(
        pairs,
        decisions=decisions,
        policy=policy,
        batch_id=batch_id,
        window_id=window_id,
        ledger_id=ledger_id,
    )
    window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_from_directories(
        pairs, policy=policy, batch_id=batch_id, window_id=window_id
    )
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime import (
        run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_from_directories,
    )

    packet_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_from_directories(
        pairs, policy=policy, batch_id=batch_id, window_id=window_id
    )
    assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        window, packet_runtime
    )
    return _runtime(ledger, window, assurance, runtime_id=runtime_id)


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime:
    """Verify stage addresses and runtime aggregate address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
    ):
        raise ValidationError("review runtime verification requires a typed runtime")
    for stage in value.stages:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_stage(
                stage
            )
            != stage.content_address
        ):
            raise ValidationError("review runtime stage address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review runtime address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "stage_id",
        "kind",
        "state",
        "input_address",
        "output_address",
        "accepted",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.stages:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review Runtime",
        "",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- stages: `{value.stage_count}`; completed: `{value.completed_count}`; blocked: `{value.blocked_count}`; skipped: `{value.skipped_count}`",
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


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
    *,
    resource: str = "summary",
    kind: str | None = None,
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded runtime summary or stage page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
        value
    )
    if resource not in {"summary", "stages"}:
        raise ValidationError("review runtime query resource is invalid")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review runtime query offset is invalid")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT
    ):
        raise ValidationError("review runtime query limit is invalid")
    if accepted is not None and not isinstance(accepted, bool):
        raise ValidationError("review runtime accepted filter is invalid")
    if text is not None:
        text = _text(text, "review runtime query text")
    if resource == "summary":
        rows = [value.summary()]
        index_used = "runtime_id"
    else:
        rows = [item.to_dict() for item in value.stages]
        if kind is not None:
            rows = [row for row in rows if row["kind"] == kind]
        if state is not None:
            rows = [row for row in rows if row["state"] == state]
        if accepted is not None:
            rows = [row for row in rows if row["accepted"] is accepted]
        if text is not None:
            rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
        index_used = "ordinal"
    body = {
        "resource": resource,
        "query": {"kind": kind, "state": state, "accepted": accepted, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
        "release_ready": value.release_ready,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a runtime query envelope."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review runtime query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX
        + "-query",
    )
    if value["content_address"] != expected:
        raise ValidationError("review runtime query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query(
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
        "release_ready",
        "reference_address",
        "content_address",
        "ordinal",
        "stage_id",
        "kind",
        "state",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            writer.writerow(envelope | dict(row))
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review Runtime Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Kind | State | Detail |",
        "|---:|---|---|---|",
    ]
    for row in value.get("items", []):
        lines.append(
            f"| {row.get('ordinal')} | {row.get('kind')} | {row.get('state')} | {row.get('detail')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_schema() -> (
    dict[str, Any]
):
    """Describe the fail-closed runtime."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_BOUNDARY,
        "stages": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind
        ],
        "stage_states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState
        ],
        "missing_head": "blocked",
        "mutates_store": False,
        "release_requires": [
            "accepted",
            "head",
            "window_release_ready",
            "assurance_release_ready",
            "promote_decision",
        ],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_capabilities() -> (
    dict[str, Any]
):
    """Declare review runtime operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_VERSION,
        "operations": ["run", "run_from_directories", "verify", "json", "csv", "markdown", "query"],
        "stage_count": 7,
        "fail_closed": True,
        "mutates_store": False,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_schema() -> (
    dict[str, Any]
):
    """Describe bounded runtime stage queries."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX
        + "-query-v1",
        "resources": {"summary": ["summary"], "stages": ["stages"]},
        "filters": ["kind", "state", "accepted", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_query_capabilities() -> (
    dict[str, Any]
):
    """Declare runtime query and export operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX
        + "-query-v1",
        "operations": ["summary", "stages", "filter", "page", "json", "csv", "markdown", "verify"],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime"
    )
    or name.startswith(
        "run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime"
    )
]
