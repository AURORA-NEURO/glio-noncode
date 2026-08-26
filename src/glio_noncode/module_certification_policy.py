"""Independent policy evaluation for the module certification matrix."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    CertificationCheckKind,
    CertificationCheckPlane,
    CertificationGateState,
    ModuleCertificationGate,
    ModuleCertificationGateCheck,
    ModuleCertificationMatrix,
    ModuleCertificationPolicy,
    ModuleCertificationTaskPlan,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def build_module_certification_policy(
    *,
    policy_id: str = "glio-noncode-module-certification-default",
    minimum_score: float = 0.80,
    minimum_certified_percent: float = 80.0,
    maximum_blocked_count: int = 0,
    maximum_review_count: int = 10000,
    require_tests_for_domain: bool = True,
    require_documentation_for_integration: bool = True,
    require_export_for_public_symbols: bool = True,
    allow_not_applicable: bool = True,
) -> ModuleCertificationPolicy:
    """Create a deterministic policy with explicit release thresholds."""

    body = {
        "policy_id": policy_id,
        "minimum_score": minimum_score,
        "minimum_certified_percent": minimum_certified_percent,
        "maximum_blocked_count": maximum_blocked_count,
        "maximum_review_count": maximum_review_count,
        "require_tests_for_domain": require_tests_for_domain,
        "require_documentation_for_integration": require_documentation_for_integration,
        "require_export_for_public_symbols": require_export_for_public_symbols,
        "allow_not_applicable": allow_not_applicable,
    }
    return ModuleCertificationPolicy(
        **body, content_address=_address(body, "module-certification-policy")
    )


def default_module_certification_policy() -> ModuleCertificationPolicy:
    """Return the repository's conservative release policy."""

    return build_module_certification_policy()


def _check(
    check_id: str,
    plane: CertificationCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleCertificationGateCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleCertificationGateCheck(
        **body, content_address=_address(body, "module-certification-gate-check")
    )


def _check_count(matrix: ModuleCertificationMatrix, kind: CertificationCheckKind) -> int:
    return sum(
        check.state.value == "failed"
        for row in matrix.rows
        for check in row.checks
        if check.kind is kind
    )


def _domain_without_tests(matrix: ModuleCertificationMatrix) -> tuple[str, ...]:
    return tuple(
        row.module_id
        for row in matrix.rows
        if row.role == "domain"
        and any(
            check.kind is CertificationCheckKind.TEST and check.state.value == "failed"
            for check in row.checks
        )
    )


def _integration_without_docs(matrix: ModuleCertificationMatrix) -> tuple[str, ...]:
    return tuple(
        row.module_id
        for row in matrix.rows
        if row.role == "integration"
        and any(
            check.kind is CertificationCheckKind.DOCUMENTATION and check.state.value == "failed"
            for check in row.checks
        )
    )


def evaluate_module_certification_gate(
    matrix: ModuleCertificationMatrix,
    plan: ModuleCertificationTaskPlan,
    policy: ModuleCertificationPolicy | None = None,
) -> ModuleCertificationGate:
    """Evaluate independent aggregate checks over a complete matrix."""

    if not isinstance(matrix, ModuleCertificationMatrix):
        raise ValidationError("certification gate requires a typed matrix")
    if not isinstance(plan, ModuleCertificationTaskPlan):
        raise ValidationError("certification gate requires a typed task plan")
    selected = policy or default_module_certification_policy()
    if matrix.module_count == 0:
        raise ValidationError("certification gate requires at least one module")
    domain_gaps = _domain_without_tests(matrix)
    integration_gaps = _integration_without_docs(matrix)
    failed_checks = (
        matrix.module_count * matrix.check_kind_count
        - sum(row.not_applicable_count for row in matrix.rows)
        - sum(row.passed_count for row in matrix.rows)
    )
    not_applicable = sum(row.not_applicable_count for row in matrix.rows)
    checks = (
        _check(
            "input-acceptance",
            CertificationCheckPlane.INVENTORY,
            matrix.accepted and plan.accepted,
            matrix.accepted and plan.accepted,
            True,
            "inventory and remediation plan are accepted inputs",
        ),
        _check(
            "minimum-overall-score",
            CertificationCheckPlane.COVERAGE,
            matrix.overall_score >= selected.minimum_score,
            matrix.overall_score,
            selected.minimum_score,
            "aggregate module score meets the selected threshold",
        ),
        _check(
            "minimum-certified-percent",
            CertificationCheckPlane.COVERAGE,
            matrix.module_count > 0
            and matrix.certified_count * 100.0 / matrix.module_count
            >= selected.minimum_certified_percent,
            round(
                matrix.certified_count * 100.0 / matrix.module_count,
                6,
            ),
            selected.minimum_certified_percent,
            "certified module share meets the selected threshold",
        ),
        _check(
            "blocked-limit",
            CertificationCheckPlane.POLICY,
            matrix.blocked_count <= selected.maximum_blocked_count,
            matrix.blocked_count,
            selected.maximum_blocked_count,
            "blocked module count is within policy",
        ),
        _check(
            "review-limit",
            CertificationCheckPlane.POLICY,
            matrix.review_count <= selected.maximum_review_count,
            matrix.review_count,
            selected.maximum_review_count,
            "review module count is within policy",
        ),
        _check(
            "domain-test-coverage",
            CertificationCheckPlane.COVERAGE,
            not selected.require_tests_for_domain or not domain_gaps,
            len(domain_gaps),
            0 if selected.require_tests_for_domain else "not required",
            "domain modules have static test evidence",
        ),
        _check(
            "integration-documentation",
            CertificationCheckPlane.COVERAGE,
            not selected.require_documentation_for_integration or not integration_gaps,
            len(integration_gaps),
            0 if selected.require_documentation_for_integration else "not required",
            "integration modules have documentation evidence",
        ),
        _check(
            "public-export-coverage",
            CertificationCheckPlane.PUBLIC,
            not selected.require_export_for_public_symbols
            or _check_count(matrix, CertificationCheckKind.EXPORT) == 0,
            _check_count(matrix, CertificationCheckKind.EXPORT),
            0 if selected.require_export_for_public_symbols else "not required",
            "public module surfaces are represented by package exports",
        ),
        _check(
            "not-applicable-policy",
            CertificationCheckPlane.POLICY,
            selected.allow_not_applicable or not_applicable == 0,
            not_applicable,
            "allowed" if selected.allow_not_applicable else 0,
            "not-applicable checks follow the selected policy",
        ),
        _check(
            "failed-check-closure",
            CertificationCheckPlane.COVERAGE,
            failed_checks == matrix.gap_count,
            failed_checks,
            matrix.gap_count,
            "every failed check has exactly one remediation gap",
        ),
        _check(
            "task-gap-closure",
            CertificationCheckPlane.POLICY,
            all(
                gap_id in {gap.gap_id for gap in matrix.gaps}
                for task in plan.tasks
                for gap_id in task.gap_ids
            ),
            sum(len(task.gap_ids) for task in plan.tasks),
            "all task gap references exist",
            "remediation tasks reference existing gaps",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "matrix_address": matrix.content_address,
        "plan_address": plan.content_address,
        "policy": selected,
        "checks": checks,
        "state": CertificationGateState.ACCEPTED if accepted else CertificationGateState.BLOCKED,
        "accepted": accepted,
    }
    return ModuleCertificationGate(
        **body, content_address=_address(body, "module-certification-gate")
    )


def module_certification_policy_json(policy: ModuleCertificationPolicy) -> str:
    return canonical_json(policy.to_dict()) + "\n"


def module_certification_policy_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-policy-v1",
        "boundary": "public_aggregate_module_certification_policy",
        "policy_fields": [
            "policy_id",
            "minimum_score",
            "minimum_certified_percent",
            "maximum_blocked_count",
            "maximum_review_count",
            "require_tests_for_domain",
            "require_documentation_for_integration",
            "require_export_for_public_symbols",
            "allow_not_applicable",
            "content_address",
        ],
        "check_planes": [item.value for item in CertificationCheckPlane],
        "gate_states": [item.value for item in CertificationGateState],
        "accepted_rule": "all independent policy checks must pass",
    }


def module_certification_policy_capabilities() -> dict[str, Any]:
    operations = (
        "build_default_policy",
        "build_threshold_policy",
        "evaluate_input_acceptance",
        "evaluate_overall_score",
        "evaluate_certified_share",
        "evaluate_blocked_limit",
        "evaluate_review_limit",
        "evaluate_domain_test_coverage",
        "evaluate_integration_documentation",
        "evaluate_public_exports",
        "evaluate_not_applicable_policy",
        "evaluate_failed_check_closure",
        "evaluate_task_gap_closure",
    )
    return {
        "version": "module-certification-policy-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "independent": True,
        "read_only": True,
        "deterministic": True,
    }


__all__ = [
    "build_module_certification_policy",
    "default_module_certification_policy",
    "evaluate_module_certification_gate",
    "module_certification_policy_capabilities",
    "module_certification_policy_json",
    "module_certification_policy_schema",
]
