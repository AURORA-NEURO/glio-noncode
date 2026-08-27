"""Execute the archive-store replication lifecycle as one addressed receipt."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store import (
    load_module_workbench_execution_packet_archive_store,
    verify_module_workbench_execution_packet_archive_store,
)
from .module_workbench_execution_packet_archive_store_replication import (
    apply_module_workbench_execution_packet_archive_store_replication,
    build_module_workbench_execution_packet_archive_store_promotion,
    build_module_workbench_execution_packet_archive_store_replication,
)
from .module_workbench_execution_packet_archive_store_replication_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStorePromotion,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
)
from .module_workbench_execution_packet_archive_store_replication_runtime_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState,
    address_module_workbench_execution_packet_archive_store_replication_runtime,
    address_module_workbench_execution_packet_archive_store_replication_runtime_stage,
)
from .serialization import canonical_json, content_hash


def _stage(
    ordinal: int,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind,
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage:
    accepted = (
        state is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED
    )
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "state": state,
        "artifact_address": artifact_address,
        "accepted": accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage(
        **body,
        content_address="pending:replication-runtime-stage",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_runtime_stage(
            provisional
        ),
    )


def _runtime(
    plan: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    receipt: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt | None,
    promotion: ModuleWorkbenchExecutionPacketArchiveStorePromotion,
    stages: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage, ...],
    *,
    apply_requested: bool,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime:
    body = {
        "replication_id": plan.replication_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_RUNTIME_BOUNDARY,
        "source_store_id": plan.source_store_id,
        "target_store_id": plan.target_store_id,
        "plan_address": plan.content_address,
        "receipt_address": receipt.content_address if receipt is not None else None,
        "promotion_address": promotion.content_address,
        "stages": stages,
        "stage_count": len(stages),
        "completed_count": sum(
            item.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED
            for item in stages
        ),
        "skipped_count": sum(
            item.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.SKIPPED
            for item in stages
        ),
        "blocked_count": sum(
            item.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED
            for item in stages
        ),
        "apply_requested": apply_requested,
        "object_copy_count": plan.object_copy_count,
        "operation_copy_count": plan.operation_copy_count,
        "required_byte_count": plan.required_byte_count,
        "accepted": all(item.accepted for item in stages),
        "detail": (
            "replication plan was verified, optionally applied, and promotion was evaluated"
            if all(item.accepted for item in stages)
            else "replication runtime contains a blocked stage"
        ),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime(
        **body,
        content_address="pending:replication-runtime",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_runtime(
            provisional
        ),
    )


def run_module_workbench_execution_packet_archive_store_replication_runtime(
    source: Any,
    target: Any,
    *,
    replication_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-runtime"
    ),
    expected_target_head_address: str | None = None,
    destination: str | Path | None = None,
    apply: bool = False,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime:
    """Run plan, verification, optional apply, and promotion evaluation.

    ``source`` and ``target`` may be typed stores or persisted directories.
    The runtime receipt never contains those input locations.
    """

    source_store = (
        source
        if hasattr(source, "content_address")
        else load_module_workbench_execution_packet_archive_store(source)
    )
    target_store = (
        target
        if hasattr(target, "content_address")
        else load_module_workbench_execution_packet_archive_store(target)
    )
    plan = build_module_workbench_execution_packet_archive_store_replication(
        source_store,
        target_store,
        replication_id=replication_id,
        expected_target_head_address=expected_target_head_address,
    )
    stages: list[ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStage] = [
        _stage(
            0,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.PLAN,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED
            if plan.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED,
            plan.content_address,
            "source and target replication plan built",
        )
    ]
    source_verification = verify_module_workbench_execution_packet_archive_store(source_store)
    stages.append(
        _stage(
            1,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.VERIFY_SOURCE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED
            if source_verification.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED,
            source_verification.content_address,
            "source store verification completed",
        )
    )
    target_verification = verify_module_workbench_execution_packet_archive_store(target_store)
    stages.append(
        _stage(
            2,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.VERIFY_TARGET,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED
            if target_verification.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED,
            target_verification.content_address,
            "target store verification completed",
        )
    )
    stages.append(
        _stage(
            3,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.RECONCILE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED
            if plan.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED,
            plan.content_address,
            "ancestry, object actions, operation actions, and public boundary reconciled",
        )
    )
    receipt: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt | None = None
    if apply:
        if destination is None:
            stages.append(
                _stage(
                    4,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.APPLY,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED,
                    plan.content_address,
                    "apply was requested without a destination",
                )
            )
        elif plan.accepted:
            receipt = apply_module_workbench_execution_packet_archive_store_replication(
                plan,
                source_store,
                target_store,
                destination=destination,
                expected_target_head_address=expected_target_head_address,
                allow_existing=allow_existing,
            )
            stages.append(
                _stage(
                    4,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.APPLY,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED,
                    receipt.content_address,
                    "replication applied and destination reloaded",
                )
            )
        else:
            stages.append(
                _stage(
                    4,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.APPLY,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED,
                    plan.content_address,
                    "apply was blocked because the replication plan was not accepted",
                )
            )
    else:
        stages.append(
            _stage(
                4,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.APPLY,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.SKIPPED,
                plan.content_address,
                "apply was not requested; plan remains a read-only projection",
            )
        )
    promotion = build_module_workbench_execution_packet_archive_store_promotion(plan, receipt)
    stages.append(
        _stage(
            5,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.PROMOTE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED
            if promotion.accepted or plan.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.BLOCKED,
            promotion.content_address,
            "promotion decision evaluated without exposing filesystem locations",
        )
    )
    stages.append(
        _stage(
            6,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageKind.COMPLETE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntimeStageState.COMPLETED,
            promotion.content_address,
            "replication lifecycle closed; runtime acceptance reflects any blocked prior stage",
        )
    )
    return _runtime(plan, receipt, promotion, tuple(stages), apply_requested=apply)


def verify_module_workbench_execution_packet_archive_store_replication_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime:
    """Verify nested stage addresses and the complete runtime address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime):
        raise ValidationError("replication runtime verification requires a typed runtime")
    for stage in value.stages:
        if (
            address_module_workbench_execution_packet_archive_store_replication_runtime_stage(stage)
            != stage.content_address
        ):
            raise ValidationError("replication runtime stage address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_runtime(value)
        != value.content_address
    ):
        raise ValidationError("replication runtime address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_runtime(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_runtime(value)
    output = io.StringIO(newline="")
    fields = ("ordinal", "kind", "state", "artifact_address", "accepted", "detail")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for stage in value.stages:
        writer.writerow(stage.to_dict())
    return output.getvalue()


def query_module_workbench_execution_packet_archive_store_replication_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime,
    *,
    resource: str = "summary",
    state: str | None = None,
    kind: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return bounded runtime summary or stage rows."""

    verify_module_workbench_execution_packet_archive_store_replication_runtime(value)
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("replication runtime query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [value.summary()]
    elif normalized == "stages":
        rows = [item.to_dict() for item in value.stages]
        if state:
            rows = [item for item in rows if item.get("state") == state]
        if kind:
            rows = [item for item in rows if item.get("kind") == kind]
    else:
        raise ValidationError("unsupported replication runtime resource")
    items = rows[offset : offset + limit]
    body = {
        "resource": normalized,
        "query": {"state": state, "kind": kind},
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "reference_address": value.content_address,
        "items": items,
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-archive-store-replication-runtime-query",
        )
    }
