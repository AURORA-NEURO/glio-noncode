"""Run the complete static module workbench chain as one typed artifact."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_certification import build_module_certification
from .module_certification_lineage import build_module_certification_lineage
from .module_certification_quality import build_module_certification_quality
from .module_inventory import build_module_inventory
from .module_inventory_contracts import ModuleInventory
from .module_workbench import build_module_workbench
from .module_workbench_audit import audit_module_workbench
from .module_workbench_contracts import ModuleWorkbenchReport
from .module_workbench_policy import (
    default_module_workbench_policy,
    evaluate_module_workbench_policy,
)
from .module_workbench_policy_contracts import ModuleWorkbenchGate, ModuleWorkbenchPolicy
from .module_workbench_runtime_contracts import (
    MODULE_WORKBENCH_RUNTIME_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RUNTIME_MAX_LIMIT,
    MODULE_WORKBENCH_RUNTIME_VERSION,
    ModuleWorkbenchRuntime,
    ModuleWorkbenchStage,
    ModuleWorkbenchStageKind,
    ModuleWorkbenchStageState,
    address_module_workbench_stage,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _stage(
    kind: ModuleWorkbenchStageKind,
    accepted: bool,
    artifact_address: str,
    detail: str,
) -> ModuleWorkbenchStage:
    body = {
        "kind": kind,
        "state": (
            ModuleWorkbenchStageState.COMPLETED if accepted else ModuleWorkbenchStageState.BLOCKED
        ),
        "accepted": accepted,
        "artifact_address": artifact_address,
        "detail": detail,
    }
    provisional = ModuleWorkbenchStage(**body, content_address="pending")
    return ModuleWorkbenchStage(
        **body,
        content_address=address_module_workbench_stage(provisional),
    )


def _runtime(
    inventory: ModuleInventory,
    matrix: Any,
    lineage: Any,
    quality: Any,
    workbench: ModuleWorkbenchReport,
    policy: ModuleWorkbenchPolicy,
    gate: ModuleWorkbenchGate,
    audit: Any,
) -> ModuleWorkbenchRuntime:
    stages = (
        _stage(
            ModuleWorkbenchStageKind.INVENTORY,
            inventory.accepted,
            inventory.content_address,
            f"indexed {inventory.module_count} source modules",
        ),
        _stage(
            ModuleWorkbenchStageKind.CERTIFICATION,
            matrix.accepted,
            matrix.content_address,
            f"evaluated {matrix.module_count} modules across {matrix.check_kind_count} checks",
        ),
        _stage(
            ModuleWorkbenchStageKind.LINEAGE,
            lineage.accepted,
            lineage.content_address,
            f"linked {lineage.evidence_count} evidence rows and {lineage.edge_count} graph edges",
        ),
        _stage(
            ModuleWorkbenchStageKind.QUALITY,
            quality.accepted,
            quality.content_address,
            f"measured {quality.evidence_coverage_percent:.2f}% evidence coverage",
        ),
        _stage(
            ModuleWorkbenchStageKind.WORKBENCH,
            workbench.accepted,
            workbench.content_address,
            f"planned {len(workbench.tasks)} module implementation tasks",
        ),
        _stage(
            ModuleWorkbenchStageKind.POLICY,
            gate.accepted,
            gate.content_address,
            f"evaluated policy {policy.policy_id}",
        ),
        _stage(
            ModuleWorkbenchStageKind.AUDIT,
            audit.accepted,
            audit.content_address,
            f"ran {len(audit.checks)} independent invariant checks",
        ),
    )
    body = {
        "inventory_address": inventory.content_address,
        "certification_address": matrix.content_address,
        "lineage_address": lineage.content_address,
        "quality_address": quality.content_address,
        "workbench_address": workbench.content_address,
        "policy_address": policy.content_address,
        "gate_address": gate.content_address,
        "audit_address": audit.content_address,
        "stages": stages,
        "accepted": all(item.accepted for item in stages),
    }
    provisional = ModuleWorkbenchRuntime(**body, content_address="pending")
    runtime_body = provisional.to_dict()
    runtime_body.pop("content_address", None)
    return ModuleWorkbenchRuntime(
        **body,
        content_address=_address(runtime_body, "module-workbench-runtime"),
    )


def run_module_workbench(
    source_root: str | Path | None = None,
    *,
    test_root: str | Path | None = None,
    docs_root: str | Path | None = None,
    policy: ModuleWorkbenchPolicy | None = None,
) -> ModuleWorkbenchRuntime:
    """Run inventory through independent workbench audit in one pass."""

    inventory = build_module_inventory(source_root, test_root=test_root)
    matrix = build_module_certification(
        inventory,
        source_root=source_root,
        test_root=test_root,
        docs_root=docs_root,
    )
    lineage = build_module_certification_lineage(
        inventory,
        matrix=matrix,
        source_root=source_root,
        test_root=test_root,
        docs_root=docs_root,
    )
    quality = build_module_certification_quality(matrix, lineage)
    workbench = build_module_workbench(inventory, matrix, lineage, quality)
    selected_policy = policy or default_module_workbench_policy()
    gate = evaluate_module_workbench_policy(workbench, selected_policy)
    audit = audit_module_workbench(workbench)
    return _runtime(
        inventory,
        matrix,
        lineage,
        quality,
        workbench,
        selected_policy,
        gate,
        audit,
    )


def verify_module_workbench_runtime(value: ModuleWorkbenchRuntime) -> ModuleWorkbenchRuntime:
    """Verify stage addresses and aggregate runtime content address."""

    if not isinstance(value, ModuleWorkbenchRuntime):
        raise ValidationError("workbench runtime verification requires a typed runtime")
    for stage in value.stages:
        if address_module_workbench_stage(stage) != stage.content_address:
            raise ValidationError(f"workbench runtime stage address mismatch: {stage.kind.value}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-runtime") != value.content_address:
        raise ValidationError("module workbench runtime address mismatch")
    return value


def query_module_workbench_runtime(
    value: ModuleWorkbenchRuntime,
    *,
    resource: str = "stages",
    state: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RUNTIME_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded runtime stage or summary page."""

    if not isinstance(value, ModuleWorkbenchRuntime):
        raise ValidationError("workbench runtime query requires a typed runtime")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RUNTIME_MAX_LIMIT:
        raise ValidationError("workbench runtime paging is invalid")
    if resource == "stages":
        rows = [item.to_dict() for item in value.stages]
    elif resource == "summary":
        rows = [value.to_dict(include_stages=False)]
    else:
        raise ValidationError("workbench runtime resource must be stages or summary")
    if state:
        rows = [item for item in rows if item.get("state") == state]
    if accepted is not None:
        rows = [item for item in rows if item.get("accepted") is accepted]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "runtime_address": value.content_address,
        "query": {"resource": resource, "state": state, "accepted": accepted, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-runtime-query")}


def module_workbench_runtime_csv(value: ModuleWorkbenchRuntime) -> str:
    fields = (
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


def module_workbench_runtime_json(value: ModuleWorkbenchRuntime) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_runtime_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RUNTIME_VERSION,
        "boundary": "public_aggregate_module_workbench_runtime",
        "stage_order": [item.value for item in ModuleWorkbenchStageKind],
        "stage_states": [item.value for item in ModuleWorkbenchStageState],
        "resources": ["stages", "summary"],
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_runtime_capabilities() -> dict[str, Any]:
    operations = (
        "run_inventory_stage",
        "run_certification_stage",
        "run_lineage_stage",
        "run_quality_stage",
        "run_workbench_stage",
        "run_policy_stage",
        "run_audit_stage",
        "query_stages",
        "summarize_runtime",
        "export_json",
        "export_csv",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_RUNTIME_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "module_workbench_runtime_capabilities",
    "module_workbench_runtime_csv",
    "module_workbench_runtime_json",
    "module_workbench_runtime_schema",
    "query_module_workbench_runtime",
    "run_module_workbench",
    "verify_module_workbench_runtime",
]
