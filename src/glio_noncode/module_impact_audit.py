"""Independent integrity and public-boundary audit for impact closures."""

from __future__ import annotations

from typing import Any

from .errors import ValidationError
from .module_impact_contracts import (
    ImpactCheckPlane,
    ModuleImpactAudit,
    ModuleImpactAuditCheck,
    ModuleImpactDiff,
    ModuleImpactGate,
    ModuleImpactReport,
    ModuleImpactVerificationPlan,
)
from .run_workspace import _has_forbidden_key
from .serialization import content_hash


def _check(
    check_id: str,
    plane: ImpactCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleImpactAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleImpactAuditCheck(
        **body, content_address=content_hash(body, prefix="module-impact-audit-check")
    )


def audit_module_impact(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
    plan: ModuleImpactVerificationPlan,
    gate: ModuleImpactGate,
) -> ModuleImpactAudit:
    """Audit row identity, closure references, conservation, and public shape."""

    if not all(
        isinstance(
            item,
            (ModuleImpactDiff, ModuleImpactReport, ModuleImpactVerificationPlan, ModuleImpactGate),
        )
        for item in (diff, report, plan, gate)
    ):
        raise ValidationError("impact audit requires typed closure objects")
    direct_ids = {item.module_id for item in diff.changes if item.kind.value != "unchanged"}
    assessment_ids = {item.module_id for item in report.assessments}
    task_ids = {item.module_id for item in plan.tasks}
    changed_ids = {item.module_id for item in diff.changes}
    paths_valid = all(
        path.split("->")[0] in direct_ids
        and path.split("->")[-1] == item.module_id
        and len(path.split("->")) - 1 == item.distance
        for item in report.assessments
        for path in item.paths
    )
    checks = (
        _check(
            "diff-input-addresses",
            ImpactCheckPlane.INPUT,
            bool(diff.left_inventory_address and diff.right_inventory_address),
            bool(diff.left_inventory_address and diff.right_inventory_address),
            True,
            "both inventory input addresses are present",
        ),
        _check(
            "change-row-order",
            ImpactCheckPlane.DIFF,
            tuple(item.module_id for item in diff.changes) == tuple(sorted(changed_ids)),
            len(diff.changes),
            len(changed_ids),
            "module change rows are unique and sorted",
        ),
        _check(
            "dependency-row-order",
            ImpactCheckPlane.DIFF,
            tuple(item.key for item in diff.dependencies)
            == tuple(sorted(item.key for item in diff.dependencies)),
            len(diff.dependencies),
            len(diff.dependencies),
            "dependency change rows are key ordered",
        ),
        _check(
            "direct-impact-closure",
            ImpactCheckPlane.GRAPH,
            direct_ids.issubset(assessment_ids),
            len(direct_ids & assessment_ids),
            len(direct_ids),
            "every direct change has an impact assessment",
        ),
        _check(
            "impact-paths",
            ImpactCheckPlane.GRAPH,
            paths_valid,
            sum(paths_valid for item in report.assessments for _ in item.paths),
            sum(len(item.paths) for item in report.assessments),
            "impact paths terminate at their assessment module",
        ),
        _check(
            "impact-count-conservation",
            ImpactCheckPlane.GRAPH,
            report.direct_count + report.dependent_count + report.transitive_count
            == report.impact_count,
            report.direct_count + report.dependent_count + report.transitive_count,
            report.impact_count,
            "impact propagation counters conserve assessment rows",
        ),
        _check(
            "verification-closure",
            ImpactCheckPlane.VERIFICATION,
            task_ids.issubset(assessment_ids | {item.source_module for item in diff.dependencies}),
            len(task_ids),
            len(task_ids),
            "verification tasks refer to impact or dependency sources",
        ),
        _check(
            "gate-references",
            ImpactCheckPlane.POLICY,
            gate.diff_address == diff.content_address
            and gate.impact_address == report.content_address
            and gate.plan_address == plan.content_address,
            True,
            True,
            "gate references the same diff, report, and plan",
        ),
        _check(
            "public-boundary",
            ImpactCheckPlane.PUBLIC,
            not _has_forbidden_key(
                {
                    "diff": diff.to_dict(include_rows=False),
                    "report": report.to_dict(include_rows=False),
                    "plan": plan.to_dict(include_rows=False),
                    "gate": gate.to_dict(),
                }
            ),
            True,
            True,
            "aggregate projections contain no forbidden public keys",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"diff_address": diff.content_address, "checks": checks, "accepted": accepted}
    return ModuleImpactAudit(
        **body, content_address=content_hash(body, prefix="module-impact-audit")
    )


def module_impact_audit_schema() -> dict[str, Any]:
    return {
        "version": "module-impact-audit-v1",
        "boundary": "public_aggregate_module_impact_audit",
        "check_fields": [
            "check_id",
            "plane",
            "passed",
            "observed",
            "required",
            "detail",
            "content_address",
        ],
        "planes": [item.value for item in ImpactCheckPlane],
        "checks": [
            "diff-input-addresses",
            "change-row-order",
            "dependency-row-order",
            "direct-impact-closure",
            "impact-paths",
            "impact-count-conservation",
            "verification-closure",
            "gate-references",
            "public-boundary",
        ],
        "accepted_rule": "all independent audit checks must pass",
    }


def module_impact_audit_capabilities() -> dict[str, Any]:
    operations = (
        "audit_input_addresses",
        "audit_change_order",
        "audit_dependency_order",
        "audit_direct_closure",
        "audit_impact_paths",
        "audit_count_conservation",
        "audit_verification_closure",
        "audit_gate_references",
        "audit_public_boundary",
    )
    return {
        "version": "module-impact-audit-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "independent": True,
        "read_only": True,
    }


__all__ = [
    "audit_module_impact",
    "module_impact_audit_capabilities",
    "module_impact_audit_schema",
]
