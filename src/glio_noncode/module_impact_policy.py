"""Policy evaluation for module-change impact release decisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_impact_contracts import (
    ImpactCheckPlane,
    ImpactGateState,
    ModuleImpactDiff,
    ModuleImpactGate,
    ModuleImpactGateCheck,
    ModuleImpactPolicy,
    ModuleImpactReport,
    ModuleImpactVerificationPlan,
)
from .serialization import content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _check(
    check_id: str,
    plane: ImpactCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleImpactGateCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleImpactGateCheck(**body, content_address=_address(body, "module-impact-gate-check"))


def default_module_impact_policy() -> ModuleImpactPolicy:
    """Return conservative but usable defaults for a static change gate."""

    body = {
        "policy_id": "glio-noncode-module-impact-default",
        "max_critical": 0,
        "max_high": 10000,
        "allow_removed_modules": False,
        "require_tests_for_direct_changes": False,
        "require_clean_inputs": True,
        "max_unresolved_direct": 10000,
        "min_verification_task_count": 0,
    }
    return ModuleImpactPolicy(**body, content_address=_address(body, "module-impact-policy"))


def build_module_impact_policy(
    *,
    policy_id: str = "glio-noncode-module-impact-default",
    max_critical: int = 0,
    max_high: int = 10000,
    allow_removed_modules: bool = False,
    require_tests_for_direct_changes: bool = False,
    require_clean_inputs: bool = True,
    max_unresolved_direct: int = 10000,
    min_verification_task_count: int = 0,
) -> ModuleImpactPolicy:
    """Construct a policy while keeping its address independent of machine paths."""

    body = {
        "policy_id": policy_id,
        "max_critical": max_critical,
        "max_high": max_high,
        "allow_removed_modules": allow_removed_modules,
        "require_tests_for_direct_changes": require_tests_for_direct_changes,
        "require_clean_inputs": require_clean_inputs,
        "max_unresolved_direct": max_unresolved_direct,
        "min_verification_task_count": min_verification_task_count,
    }
    return ModuleImpactPolicy(**body, content_address=_address(body, "module-impact-policy"))


def _direct_unresolved_count(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
) -> int:
    direct = {item.module_id for item in report.assessments if item.distance == 0}
    return sum(
        item.source_module in direct
        and (item.right_resolved is False or item.left_resolved is False)
        for item in diff.dependencies
    )


def evaluate_module_impact_gate(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
    plan: ModuleImpactVerificationPlan,
    policy: ModuleImpactPolicy | None = None,
) -> ModuleImpactGate:
    """Evaluate a static policy over already-built impact evidence."""

    if not all(
        isinstance(item, (ModuleImpactDiff, ModuleImpactReport, ModuleImpactVerificationPlan))
        for item in (diff, report, plan)
    ):
        raise ValidationError("impact gate requires typed diff, report, and plan")
    selected = policy or default_module_impact_policy()
    direct_changes = [item for item in diff.changes if item.kind.value != "unchanged"]
    checks = [
        _check(
            "input-acceptance",
            ImpactCheckPlane.INPUT,
            (not selected.require_clean_inputs)
            or (diff.accepted and report.accepted and plan.accepted),
            diff.accepted and report.accepted and plan.accepted,
            True if selected.require_clean_inputs else False,
            "all upstream impact inputs are accepted",
        ),
        _check(
            "critical-limit",
            ImpactCheckPlane.POLICY,
            report.critical_count <= selected.max_critical,
            report.critical_count,
            selected.max_critical,
            "critical direct impact count is within policy",
        ),
        _check(
            "high-limit",
            ImpactCheckPlane.POLICY,
            report.high_count <= selected.max_high,
            report.high_count,
            selected.max_high,
            "high impact count is within policy",
        ),
        _check(
            "removed-module-policy",
            ImpactCheckPlane.POLICY,
            selected.allow_removed_modules or diff.removed_count == 0,
            diff.removed_count,
            "zero unless removals are allowed",
            "removed module policy is satisfied",
        ),
        _check(
            "direct-unresolved-limit",
            ImpactCheckPlane.GRAPH,
            _direct_unresolved_count(diff, report) <= selected.max_unresolved_direct,
            _direct_unresolved_count(diff, report),
            selected.max_unresolved_direct,
            "direct unresolved edge count is within policy",
        ),
        _check(
            "test-reference-policy",
            ImpactCheckPlane.VERIFICATION,
            (not selected.require_tests_for_direct_changes)
            or not any(item.test_reference_delta < 0 for item in direct_changes),
            sum(item.test_reference_delta < 0 for item in direct_changes),
            0 if selected.require_tests_for_direct_changes else "not required",
            "direct changes do not reduce test references under the selected policy",
        ),
        _check(
            "verification-task-minimum",
            ImpactCheckPlane.VERIFICATION,
            plan.task_count >= selected.min_verification_task_count,
            plan.task_count,
            selected.min_verification_task_count,
            "verification plan contains the required minimum task count",
        ),
        _check(
            "direct-change-closure",
            ImpactCheckPlane.DIFF,
            all(
                item.module_id in {row.module_id for row in report.assessments}
                for item in direct_changes
            ),
            len(direct_changes),
            report.direct_count,
            "every direct change has an impact assessment",
        ),
    ]
    accepted = all(item.passed for item in checks)
    body = {
        "diff_address": diff.content_address,
        "impact_address": report.content_address,
        "plan_address": plan.content_address,
        "policy": selected,
        "checks": tuple(checks),
        "state": ImpactGateState.ACCEPTED if accepted else ImpactGateState.BLOCKED,
        "accepted": accepted,
    }
    return ModuleImpactGate(**body, content_address=_address(body, "module-impact-gate"))


def module_impact_policy_schema() -> dict[str, Any]:
    """Return a machine-readable gate and policy declaration."""

    return {
        "version": "module-impact-policy-v1",
        "boundary": "public_aggregate_module_impact_policy",
        "policy_fields": [
            "policy_id",
            "max_critical",
            "max_high",
            "allow_removed_modules",
            "require_tests_for_direct_changes",
            "require_clean_inputs",
            "max_unresolved_direct",
            "min_verification_task_count",
            "content_address",
        ],
        "check_planes": [item.value for item in ImpactCheckPlane],
        "gate_states": [item.value for item in ImpactGateState],
        "verification_rule": "all policy checks must pass for accepted state",
    }


def module_impact_policy_capabilities() -> dict[str, Any]:
    operations = (
        "build_default_policy",
        "build_threshold_policy",
        "evaluate_input_acceptance",
        "evaluate_critical_limit",
        "evaluate_high_limit",
        "evaluate_removal_policy",
        "evaluate_unresolved_edge_limit",
        "evaluate_test_reference_policy",
        "evaluate_verification_minimum",
        "evaluate_direct_change_closure",
    )
    return {
        "version": "module-impact-policy-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
        "handler_execution": False,
    }


__all__ = [
    "build_module_impact_policy",
    "default_module_impact_policy",
    "evaluate_module_impact_gate",
    "module_impact_policy_capabilities",
    "module_impact_policy_schema",
]
