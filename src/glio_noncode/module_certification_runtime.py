"""Timestamp-free staged runtime for module certification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_certification import build_module_certification
from .module_certification_contracts import (
    MODULE_CERTIFICATION_VERSION,
    CertificationStageState,
    ModuleCertificationPolicy,
    ModuleCertificationRuntime,
    ModuleCertificationStage,
)
from .module_certification_policy import (
    evaluate_module_certification_gate,
)
from .module_certification_tasks import build_module_certification_task_plan
from .module_inventory import build_module_inventory
from .module_inventory_contracts import ModuleInventory
from .serialization import canonical_json, content_hash


def _stage(
    stage_id: str,
    order: int,
    input_count: int,
    output_count: int,
    issue_count: int,
    detail: str,
    state: CertificationStageState = CertificationStageState.COMPLETED,
) -> ModuleCertificationStage:
    body = {
        "stage_id": stage_id,
        "order": order,
        "state": state,
        "input_count": input_count,
        "output_count": output_count,
        "issue_count": issue_count,
        "detail": detail,
    }
    return ModuleCertificationStage(
        **body, content_address=content_hash(body, prefix="module-certification-stage")
    )


def run_module_certification(
    source_root: str | Path | None = None,
    *,
    test_root: str | Path | None = None,
    docs_root: str | Path | None = None,
    inventory: ModuleInventory | None = None,
    policy: ModuleCertificationPolicy | None = None,
    runtime_id: str = "glio-noncode-module-certification-runtime",
) -> ModuleCertificationRuntime:
    """Run static inventory, evidence, scoring, task, policy, and public stages."""

    selected = inventory or build_module_inventory(source_root, test_root=test_root)
    if not isinstance(selected, ModuleInventory):
        raise ValidationError("certification runtime inventory must be typed")
    matrix = build_module_certification(
        selected,
        source_root=source_root,
        test_root=test_root,
        docs_root=docs_root,
    )
    plan = build_module_certification_task_plan(matrix)
    gate = evaluate_module_certification_gate(matrix, plan, policy)
    stages = (
        _stage(
            "inventory",
            1,
            0,
            selected.module_count,
            len(selected.issues),
            "typed static inventory selected",
        ),
        _stage(
            "evidence",
            2,
            selected.module_count,
            matrix.module_count * matrix.check_kind_count,
            0,
            "test, documentation, package, and inventory evidence extracted",
        ),
        _stage(
            "checks",
            3,
            matrix.module_count * matrix.check_kind_count,
            matrix.module_count,
            matrix.gap_count,
            "module-level certification checks scored and conserved",
        ),
        _stage(
            "gaps",
            4,
            matrix.module_count,
            matrix.gap_count,
            matrix.gap_count,
            "failed checks converted into an ordered gap queue",
        ),
        _stage(
            "tasks",
            5,
            matrix.gap_count,
            plan.task_count,
            len(matrix.gaps) - plan.task_count,
            "one deterministic remediation task derived per gap",
            CertificationStageState.COMPLETED if plan.accepted else CertificationStageState.BLOCKED,
        ),
        _stage(
            "policy",
            6,
            len(gate.checks),
            gate.passed_count,
            len(gate.checks) - gate.passed_count,
            "aggregate certification policy evaluated",
            CertificationStageState.COMPLETED if gate.accepted else CertificationStageState.BLOCKED,
        ),
        _stage(
            "public",
            7,
            1,
            1,
            0 if gate.accepted else 1,
            "public aggregate boundary closed",
            CertificationStageState.COMPLETED if gate.accepted else CertificationStageState.BLOCKED,
        ),
    )
    body = {
        "runtime_id": runtime_id,
        "version": MODULE_CERTIFICATION_VERSION,
        "stages": stages,
        "inventory_address": selected.content_address,
        "matrix_address": matrix.content_address,
        "plan_address": plan.content_address,
        "gate_address": gate.content_address,
        "accepted": gate.accepted,
    }
    return ModuleCertificationRuntime(
        **body, content_address=content_hash(body, prefix="module-certification-runtime")
    )


def module_certification_runtime_json(runtime: ModuleCertificationRuntime) -> str:
    return canonical_json(runtime.to_dict()) + "\n"


def module_certification_runtime_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-runtime-v1",
        "boundary": "public_aggregate_module_certification_runtime",
        "stage_fields": [
            "stage_id",
            "order",
            "state",
            "input_count",
            "output_count",
            "issue_count",
            "detail",
            "content_address",
        ],
        "stage_order": ["inventory", "evidence", "checks", "gaps", "tasks", "policy", "public"],
        "stage_states": [item.value for item in CertificationStageState],
        "runtime_fields": [
            "runtime_id",
            "version",
            "stages",
            "inventory_address",
            "matrix_address",
            "plan_address",
            "gate_address",
            "accepted",
            "content_address",
        ],
        "replay_rule": (
            "same inventory, evidence bytes, and policy produce the same runtime address"
        ),
        "source_execution": False,
    }


def module_certification_runtime_capabilities() -> dict[str, Any]:
    operations = (
        "select_inventory",
        "extract_static_evidence",
        "score_module_checks",
        "build_gap_queue",
        "build_remediation_tasks",
        "evaluate_aggregate_policy",
        "close_public_boundary",
        "replay_runtime_receipt",
    )
    return {
        "version": "module-certification-runtime-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "stages": ["inventory", "evidence", "checks", "gaps", "tasks", "policy", "public"],
        "read_only": True,
        "deterministic": True,
        "timestamp_free": True,
        "source_execution": False,
    }


__all__ = [
    "module_certification_runtime_capabilities",
    "module_certification_runtime_json",
    "module_certification_runtime_schema",
    "run_module_certification",
]
