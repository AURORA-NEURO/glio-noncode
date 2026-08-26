"""Timestamp-free staged runtime for module impact assessment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_impact import build_module_impact_diff, build_module_impact_report
from .module_impact_contracts import (
    ImpactStageState,
    ModuleImpactPolicy,
    ModuleImpactRuntime,
    ModuleImpactStage,
)
from .module_impact_policy import (
    default_module_impact_policy,
    evaluate_module_impact_gate,
)
from .module_impact_verification import build_module_impact_verification_plan
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
    state: ImpactStageState = ImpactStageState.COMPLETED,
) -> ModuleImpactStage:
    body = {
        "stage_id": stage_id,
        "order": order,
        "state": state,
        "input_count": input_count,
        "output_count": output_count,
        "issue_count": issue_count,
        "detail": detail,
    }
    return ModuleImpactStage(
        **body, content_address=content_hash(body, prefix="module-impact-stage")
    )


def _inputs(
    left: ModuleInventory | None,
    right: ModuleInventory | None,
    source_root: str | Path | None,
    test_root: str | Path | None,
) -> tuple[ModuleInventory, ModuleInventory]:
    if left is not None and right is not None:
        return left, right
    if source_root is None:
        raise ValidationError("impact runtime needs two inventories or a source root")
    selected = build_module_inventory(source_root, test_root=test_root)
    return selected, selected


def run_module_impact(
    left: ModuleInventory | None = None,
    right: ModuleInventory | None = None,
    *,
    source_root: str | Path | None = None,
    test_root: str | Path | None = None,
    policy: ModuleImpactPolicy | None = None,
    runtime_id: str = "glio-noncode-module-impact-runtime",
) -> ModuleImpactRuntime:
    """Execute all static stages without running discovered source code."""

    old, new = _inputs(left, right, source_root, test_root)
    selected_policy = policy or default_module_impact_policy()
    diff = build_module_impact_diff(old, new)
    report = build_module_impact_report(old, new, diff)
    plan = build_module_impact_verification_plan(diff, report)
    gate = evaluate_module_impact_gate(diff, report, plan, selected_policy)
    stages = (
        _stage(
            "input",
            1,
            2,
            2,
            int(not (old.accepted and new.accepted)),
            "two inventory snapshots selected",
        ),
        _stage(
            "diff",
            2,
            2,
            diff.change_count,
            diff.dependency_change_count,
            "module rows and dependency edges compared",
        ),
        _stage(
            "impact",
            3,
            diff.change_count,
            report.impact_count,
            0,
            "reverse dependency impact propagated",
        ),
        _stage(
            "verification",
            4,
            report.impact_count,
            plan.task_count,
            0,
            "review and replay tasks derived",
        ),
        _stage(
            "policy",
            5,
            plan.task_count,
            gate.passed_count,
            len(gate.checks) - gate.passed_count,
            "static release policy evaluated",
            ImpactStageState.COMPLETED if gate.accepted else ImpactStageState.BLOCKED,
        ),
        _stage("replay", 6, 3, 3, 0, "addresses and deterministic stage shape recorded"),
        _stage(
            "public",
            7,
            len(gate.checks),
            1,
            0,
            "public aggregate boundary closed",
            ImpactStageState.COMPLETED if gate.accepted else ImpactStageState.BLOCKED,
        ),
    )
    body = {
        "runtime_id": runtime_id,
        "version": "module-impact-runtime-v1",
        "stages": stages,
        "left_inventory_address": old.content_address,
        "right_inventory_address": new.content_address,
        "diff_address": diff.content_address,
        "impact_address": report.content_address,
        "plan_address": plan.content_address,
        "gate_address": gate.content_address,
        "accepted": gate.accepted,
    }
    return ModuleImpactRuntime(
        **body, content_address=content_hash(body, prefix="module-impact-runtime")
    )


def module_impact_runtime_json(runtime: ModuleImpactRuntime) -> str:
    return canonical_json(runtime.to_dict()) + "\n"


def module_impact_runtime_schema() -> dict[str, Any]:
    return {
        "version": "module-impact-runtime-v1",
        "boundary": "public_aggregate_module_impact_runtime",
        "stage_order": ["input", "diff", "impact", "verification", "policy", "replay", "public"],
        "stage_states": [item.value for item in ImpactStageState],
        "runtime_fields": [
            "runtime_id",
            "version",
            "stages",
            "left_inventory_address",
            "right_inventory_address",
            "diff_address",
            "impact_address",
            "plan_address",
            "gate_address",
            "accepted",
            "content_address",
        ],
        "replay_rule": (
            "same inventory addresses, policy, and stage outputs produce the same runtime address"
        ),
    }


def module_impact_runtime_capabilities() -> dict[str, Any]:
    operations = (
        "select_inventory_pair",
        "compare_module_rows",
        "compare_dependency_edges",
        "propagate_reverse_dependency_impact",
        "derive_verification_tasks",
        "evaluate_static_policy",
        "record_deterministic_replay",
    )
    return {
        "version": "module-impact-runtime-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "stages": ["input", "diff", "impact", "verification", "policy", "replay", "public"],
        "read_only": True,
        "handler_execution": False,
        "timestamp_free": True,
    }


__all__ = [
    "module_impact_runtime_capabilities",
    "module_impact_runtime_json",
    "module_impact_runtime_schema",
    "run_module_impact",
]
