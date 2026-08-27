"""Fail-closed execution for durable release-window review stores.

The runtime is deliberately a receipt-producing layer.  It does not mutate a
store or make a second release decision.  Each stage points to an addressed
input or output, and the aggregate can therefore be replayed without trusting
process state, machine state, or an operator annotation.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_LIMIT,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-runtime-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_STAGE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-runtime-stage"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind(
    StrEnum
):
    LOAD = "load"
    VERIFY_STORE = "verify_store"
    VERIFY_LEDGER = "verify_ledger"
    VERIFY_OPERATIONS = "verify_operations"
    REPLAY = "replay"
    RESOLVE_HEAD = "resolve_head"
    EVALUATE_READINESS = "evaluate_readiness"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState(
    StrEnum
):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int = 256) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _enum(value: Any, enum_type: type[StrEnum], field: str) -> str:
    if isinstance(value, enum_type):
        return value.value
    if not isinstance(value, str):
        raise ValidationError(f"{field} is invalid")
    try:
        return enum_type(value).value
    except ValueError as exc:
        raise ValidationError(f"{field} is invalid") from exc


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStage,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_STAGE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStage:
    """One ordered, addressed runtime step."""

    def __init__(
        self,
        ordinal: int,
        stage_id: str,
        kind: str,
        state: str,
        input_address: str | None,
        output_address: str | None,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.stage_id = stage_id
        self.kind = kind
        self.state = state
        self.input_address = input_address
        self.output_address = output_address
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review store runtime stage ordinal", 31)
        _text(self.stage_id, "review store runtime stage ID", 256)
        _enum(
            self.kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind,
            "review store runtime stage kind",
        )
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState,
            "review store runtime stage state",
        )
        _address(self.input_address, "review store runtime stage input address", optional=True)
        _address(self.output_address, "review store runtime stage output address", optional=True)
        _bool(self.accepted, "review store runtime stage accepted flag")
        _text(self.detail, "review store runtime stage detail")
        _address(self.content_address, "review store runtime stage content address")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED.value
            and self.accepted
        ):
            raise ValidationError("blocked runtime stages cannot be accepted")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.SKIPPED.value
            and not self.accepted
        ):
            raise ValidationError("skipped runtime stages must be neutral")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "stage_id": self.stage_id,
            "kind": self.kind,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime:
    """Aggregate receipt for one non-mutating store execution."""

    def __init__(
        self,
        runtime_id: str,
        version: str,
        boundary: str,
        store_address: str,
        ledger_address: str,
        replay_address: str | None,
        stages: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStage,
            ...,
        ],
        stage_count: int,
        completed_count: int,
        blocked_count: int,
        skipped_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.runtime_id = runtime_id
        self.version = version
        self.boundary = boundary
        self.store_address = store_address
        self.ledger_address = ledger_address
        self.replay_address = replay_address
        self.stages = tuple(stages)
        self.stage_count = stage_count
        self.completed_count = completed_count
        self.blocked_count = blocked_count
        self.skipped_count = skipped_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.runtime_id, "review store runtime ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_VERSION
        ):
            raise ValidationError("review store runtime version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_BOUNDARY
        ):
            raise ValidationError("review store runtime boundary is invalid")
        _address(self.store_address, "review store runtime store address")
        _address(self.ledger_address, "review store runtime ledger address")
        _address(self.replay_address, "review store runtime replay address", optional=True)
        _count(self.stage_count, "review store runtime stage count", 32)
        if self.stage_count != len(self.stages) or self.stage_count != 8:
            raise ValidationError("review store runtime requires eight stages")
        for ordinal, stage in enumerate(self.stages):
            if stage.ordinal != ordinal:
                raise ValidationError("review store runtime stage ordinals are not contiguous")
        _count(self.completed_count, "review store runtime completed count", self.stage_count)
        _count(self.blocked_count, "review store runtime blocked count", self.stage_count)
        _count(self.skipped_count, "review store runtime skipped count", self.stage_count)
        counts = {
            "completed_count": sum(item.state == "completed" for item in self.stages),
            "blocked_count": sum(item.state == "blocked" for item in self.stages),
            "skipped_count": sum(item.state == "skipped" for item in self.stages),
        }
        if any(getattr(self, name) != expected for name, expected in counts.items()):
            raise ValidationError("review store runtime stage counts do not conserve")
        state = _text(self.state, "review store runtime state", 64)
        if state not in {"completed", "blocked"}:
            raise ValidationError("review store runtime state is invalid")
        if self.accepted != (state == "completed"):
            raise ValidationError("review store runtime acceptance does not conserve")
        _bool(self.release_ready, "review store runtime release-ready flag")
        if self.release_ready and not self.accepted:
            raise ValidationError("blocked review store runtimes cannot be release-ready")
        _bool(self.accepted, "review store runtime accepted flag")
        _address(self.content_address, "review store runtime content address")

    def summary(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "version": self.version,
            "boundary": self.boundary,
            "store_address": self.store_address,
            "ledger_address": self.ledger_address,
            "replay_address": self.replay_address,
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "skipped_count": self.skipped_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def _stage(
    ordinal: int,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind,
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState,
    input_address: str | None,
    output_address: str | None,
    accepted: bool,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStage:
    body = {
        "ordinal": ordinal,
        "stage_id": f"review-store-runtime-stage-{ordinal}-{kind.value}",
        "kind": kind.value,
        "state": state.value,
        "input_address": input_address,
        "output_address": output_address,
        "accepted": accepted,
        "detail": _text(detail, "review store runtime stage detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStage(
        **body, content_address="pending:stage"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_stage(
            provisional
        ),
    )


def _runtime(
    store: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    *,
    runtime_id: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        store
    )
    ledger = getattr(store, "ledger", None)
    stages: list[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStage
    ] = []
    stages.append(
        _stage(
            0,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.LOAD,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED,
            None,
            store.content_address,
            True,
            "durable review store supplied as immutable input",
        )
    )
    stages.append(
        _stage(
            1,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.VERIFY_STORE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED,
            stages[-1].content_address,
            store.content_address,
            True,
            "store aggregate and addressed checks verified",
        )
    )
    ledger_ok = (
        ledger is not None
        and ledger.content_address == store.ledger_address
        and ledger.entry_count == store.entry_count
        and ledger.head_address == store.head_address
    )
    stages.append(
        _stage(
            2,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.VERIFY_LEDGER,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED
            if ledger_ok
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED,
            stages[-1].content_address,
            ledger.content_address if ledger is not None else None,
            ledger_ok,
            "hydrated ledger agrees with the store manifest"
            if ledger_ok
            else "hydrated ledger is absent or diverges from the store manifest",
        )
    )
    operation_ok = (
        bool(store.operations)
        and all(item.accepted for item in store.operations)
        and tuple(item.ordinal for item in store.operations) == tuple(range(len(store.operations)))
    )
    stages.append(
        _stage(
            3,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.VERIFY_OPERATIONS,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED
            if operation_ok
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED,
            stages[-1].content_address,
            store.operations[-1].content_address if store.operations else None,
            operation_ok,
            "operation chain is contiguous and accepted"
            if operation_ok
            else "operation chain cannot be accepted",
        )
    )
    replay = replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        store
    )
    replay_ok = replay.accepted
    stages.append(
        _stage(
            4,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.REPLAY,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED
            if replay_ok
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED,
            stages[-1].content_address,
            replay.content_address,
            replay_ok,
            "persisted head replay matched the hydrated ledger"
            if replay_ok
            else "persisted head replay diverged or was blocked",
        )
    )
    head_ok = store.entry_count > 0 and store.head_address is not None
    stages.append(
        _stage(
            5,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.RESOLVE_HEAD,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED
            if head_ok
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED,
            stages[-1].content_address,
            store.head_address,
            head_ok,
            "review head resolved for a non-empty ledger"
            if head_ok
            else "empty review stores have no release head",
        )
    )
    readiness_ok = bool(store.release_ready and store.accepted and replay_ok and head_ok)
    stages.append(
        _stage(
            6,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.EVALUATE_READINESS,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED
            if readiness_ok
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED,
            stages[-1].content_address,
            store.content_address,
            readiness_ok,
            "store is release-ready and replay-safe"
            if readiness_ok
            else "store remains held or blocked for release",
        )
    )
    blocked = any(
        item.state
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED.value
        for item in stages
    )
    stages.append(
        _stage(
            7,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind.COMPLETE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.BLOCKED
            if blocked
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState.COMPLETED,
            stages[-1].content_address,
            store.content_address,
            not blocked,
            "runtime completed with a verified store"
            if not blocked
            else "runtime stopped because an earlier stage blocked handoff",
        )
    )
    body = {
        "runtime_id": _text(runtime_id, "review store runtime ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_BOUNDARY,
        "store_address": store.content_address,
        "ledger_address": store.ledger_address,
        "replay_address": replay.content_address,
        "stages": tuple(stages),
        "stage_count": len(stages),
        "completed_count": sum(item.state == "completed" for item in stages),
        "blocked_count": sum(item.state == "blocked" for item in stages),
        "skipped_count": sum(item.state == "skipped" for item in stages),
        "state": "blocked" if blocked else "completed",
        "release_ready": readiness_ok and not blocked,
        "accepted": not blocked,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime(
        **body, content_address="pending:runtime"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
            provisional
        ),
    )


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
    store: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    *,
    runtime_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store-runtime",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime:
    """Execute a hydrated store without changing it."""

    return _runtime(store, runtime_id=runtime_id)


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_from_directory(
    directory: str | Path,
    *,
    runtime_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store-runtime",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime:
    return run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            directory
        ),
        runtime_id=runtime_id,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime,
    ):
        raise ValidationError("review store runtime verification requires a typed runtime")
    for stage in value.stages:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_stage(
                stage
            )
            != stage.content_address
        ):
            raise ValidationError("review store runtime stage address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review store runtime address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
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
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for stage in value.stages:
        writer.writerow(stage.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
        value
    )
    lines = [
        "# Durable Release-Window Review Store Runtime",
        "",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- stages: `{value.stage_count}`; completed: `{value.completed_count}`; blocked: `{value.blocked_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | State | Accepted | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.kind} | {item.state} | {str(item.accepted).lower()} | {item.detail} |"
        for item in value.stages
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime,
    *,
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
        value
    )
    if state is not None and state not in {"completed", "blocked", "skipped"}:
        raise ValidationError("review store runtime query state is invalid")
    if accepted is not None and not isinstance(accepted, bool):
        raise ValidationError("review store runtime query accepted filter is invalid")
    if text is not None:
        text = _text(text, "review store runtime query text")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review store runtime query offset is invalid")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1
        <= limit
        <= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_LIMIT
    ):
        raise ValidationError("review store runtime query limit is invalid")
    rows = [item.to_dict() for item in value.stages]
    if state is not None:
        rows = [row for row in rows if row["state"] == state]
    if accepted is not None:
        rows = [row for row in rows if row["accepted"] is accepted]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {"state": state, "accepted": accepted, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "runtime": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_PREFIX
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review store runtime query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_PREFIX
            + "-query",
        )
        != value["content_address"]
    ):
        raise ValidationError("review store runtime query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query(
        value
    )
    output = io.StringIO(newline="")
    fields = ("ordinal", "stage_id", "kind", "state", "accepted", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value.get("items", []):
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query(
        value
    )
    lines = [
        "# Durable Review Store Runtime Query",
        "",
        f"- rows: `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Kind | State | Accepted | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | {row.get('kind', '')} | {row.get('state', '')} | {str(row.get('accepted', '')).lower()} | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_BOUNDARY,
        "stages": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageKind
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntimeStageState
        ],
        "stage_count": 8,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_VERSION,
        "operations": ["run", "verify", "query", "json", "csv", "markdown"],
        "non_mutating": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_PREFIX
        + "-query-v1",
        "filters": ["state", "accepted", "text", "offset", "limit"],
        "bounded": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME_PREFIX
        + "-query-v1",
        "resources": ["stages"],
        "exports": ["json", "csv", "markdown"],
        "identity_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_RUNTIME"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreRuntime"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime"
    )
    or name.startswith(
        "run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime"
    )
]
