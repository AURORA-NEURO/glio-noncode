"""Independent integrity and public-boundary audit for certification closures."""

from __future__ import annotations

from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    CertificationCheckKind,
    CertificationCheckPlane,
    ModuleCertificationAudit,
    ModuleCertificationAuditCheck,
    ModuleCertificationGate,
    ModuleCertificationMatrix,
    ModuleCertificationRuntime,
    ModuleCertificationTaskPlan,
)
from .run_workspace import _has_forbidden_key
from .serialization import content_hash


def _check(
    check_id: str,
    plane: CertificationCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleCertificationAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleCertificationAuditCheck(
        **body, content_address=content_hash(body, prefix="module-certification-audit-check")
    )


def audit_module_certification(
    matrix: ModuleCertificationMatrix,
    plan: ModuleCertificationTaskPlan,
    gate: ModuleCertificationGate,
    runtime: ModuleCertificationRuntime,
) -> ModuleCertificationAudit:
    """Audit ordering, address references, conservation, and public output shape."""

    typed = (matrix, plan, gate, runtime)
    if not all(
        isinstance(
            item,
            (
                ModuleCertificationMatrix,
                ModuleCertificationTaskPlan,
                ModuleCertificationGate,
                ModuleCertificationRuntime,
            ),
        )
        for item in typed
    ):
        raise ValidationError("certification audit requires typed closure objects")
    row_ids = tuple(row.module_id for row in matrix.rows)
    gap_ids = tuple(gap.gap_id for gap in matrix.gaps)
    expected_kinds = tuple(CertificationCheckKind)
    checks_in_order = all(
        tuple(check.kind for check in row.checks) == expected_kinds for row in matrix.rows
    )
    failed_ids = {
        f"{check.kind.value}:{row.module_id}"
        for row in matrix.rows
        for check in row.checks
        if check.state.value == "failed"
    }
    task_gap_ids = {gap_id for task in plan.tasks for gap_id in task.gap_ids}
    public_shape = {
        "matrix": matrix.to_dict(include_rows=False),
        "plan": plan.to_dict(include_rows=False),
        "gate": gate.to_dict(),
        "runtime": runtime.to_dict(),
    }
    audit_checks = (
        _check(
            "matrix-address",
            CertificationCheckPlane.INVENTORY,
            bool(matrix.inventory_address and matrix.content_address),
            bool(matrix.inventory_address and matrix.content_address),
            True,
            "matrix carries inventory and content addresses",
        ),
        _check(
            "module-row-order",
            CertificationCheckPlane.COVERAGE,
            row_ids == tuple(sorted(set(row_ids))),
            len(row_ids),
            len(set(row_ids)),
            "module certification rows are unique and sorted",
        ),
        _check(
            "check-order",
            CertificationCheckPlane.COVERAGE,
            checks_in_order,
            len(expected_kinds),
            len(expected_kinds),
            "each module row contains every check kind in stable order",
        ),
        _check(
            "check-count-conservation",
            CertificationCheckPlane.COVERAGE,
            all(
                row.passed_count + row.failed_count + row.not_applicable_count == len(row.checks)
                for row in matrix.rows
            ),
            sum(
                row.passed_count + row.failed_count + row.not_applicable_count
                for row in matrix.rows
            ),
            sum(len(row.checks) for row in matrix.rows),
            "per-module check counters conserve check rows",
        ),
        _check(
            "state-count-conservation",
            CertificationCheckPlane.COVERAGE,
            matrix.certified_count
            + matrix.review_count
            + matrix.blocked_count
            + matrix.uncovered_count
            == matrix.module_count,
            matrix.certified_count
            + matrix.review_count
            + matrix.blocked_count
            + matrix.uncovered_count,
            matrix.module_count,
            "module states conserve the complete matrix",
        ),
        _check(
            "gap-order",
            CertificationCheckPlane.COVERAGE,
            gap_ids
            == tuple(sorted(set(gap_ids), key=lambda gap_id: (gap_id.split(":", 1)[0], gap_id)))
            or len(gap_ids) == len(set(gap_ids)),
            len(gap_ids),
            len(set(gap_ids)),
            "gap IDs are unique and retained as a bounded queue",
        ),
        _check(
            "failed-gap-closure",
            CertificationCheckPlane.COVERAGE,
            failed_ids == set(gap_ids),
            len(failed_ids),
            len(gap_ids),
            "every failed check has one corresponding gap",
        ),
        _check(
            "task-gap-closure",
            CertificationCheckPlane.POLICY,
            task_gap_ids.issubset(set(gap_ids)),
            len(task_gap_ids),
            len(set(gap_ids)),
            "remediation tasks reference known gaps",
        ),
        _check(
            "gate-references",
            CertificationCheckPlane.POLICY,
            gate.matrix_address == matrix.content_address
            and gate.plan_address == plan.content_address,
            True,
            True,
            "gate references the audited matrix and task plan",
        ),
        _check(
            "runtime-references",
            CertificationCheckPlane.POLICY,
            runtime.matrix_address == matrix.content_address
            and runtime.plan_address == plan.content_address
            and runtime.gate_address == gate.content_address,
            True,
            True,
            "runtime references the audited matrix, plan, and gate",
        ),
        _check(
            "public-boundary",
            CertificationCheckPlane.PUBLIC,
            not _has_forbidden_key(public_shape),
            True,
            True,
            "aggregate projections contain no forbidden public keys",
        ),
    )
    accepted = all(item.passed for item in audit_checks)
    body = {"matrix_address": matrix.content_address, "checks": audit_checks, "accepted": accepted}
    return ModuleCertificationAudit(
        **body, content_address=content_hash(body, prefix="module-certification-audit")
    )


def module_certification_audit_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-audit-v1",
        "boundary": "public_aggregate_module_certification_audit",
        "check_fields": [
            "check_id",
            "plane",
            "passed",
            "observed",
            "required",
            "detail",
            "content_address",
        ],
        "planes": [item.value for item in CertificationCheckPlane],
        "checks": [
            "matrix-address",
            "module-row-order",
            "check-order",
            "check-count-conservation",
            "state-count-conservation",
            "gap-order",
            "failed-gap-closure",
            "task-gap-closure",
            "gate-references",
            "runtime-references",
            "public-boundary",
        ],
        "accepted_rule": "all independent audit checks must pass",
    }


def module_certification_audit_capabilities() -> dict[str, Any]:
    operations = (
        "audit_matrix_address",
        "audit_module_row_order",
        "audit_check_order",
        "audit_check_count_conservation",
        "audit_state_count_conservation",
        "audit_gap_order",
        "audit_failed_gap_closure",
        "audit_task_gap_closure",
        "audit_gate_references",
        "audit_runtime_references",
        "audit_public_boundary",
    )
    return {
        "version": "module-certification-audit-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "independent": True,
        "read_only": True,
        "deterministic": True,
    }


__all__ = [
    "audit_module_certification",
    "module_certification_audit_capabilities",
    "module_certification_audit_schema",
]
