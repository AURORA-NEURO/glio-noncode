"""Evaluate explicit progress policies over module execution ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_audit import audit_module_workbench_execution
from .module_workbench_execution_audit_contracts import ModuleWorkbenchExecutionAudit
from .module_workbench_execution_contracts import ModuleWorkbenchExecutionLedger
from .module_workbench_execution_policy_contracts import (
    MODULE_WORKBENCH_EXECUTION_POLICY_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_POLICY_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_POLICY_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_POLICY_VERSION,
    ModuleWorkbenchExecutionPolicy,
    ModuleWorkbenchExecutionPolicyCheck,
    ModuleWorkbenchExecutionPolicyGate,
    address_module_workbench_execution_policy,
    address_module_workbench_execution_policy_check,
    address_module_workbench_execution_policy_gate,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def build_module_workbench_execution_policy(
    *,
    policy_id: str = "module-workbench-execution-default",
    minimum_completion_percent: float = 0.0,
    minimum_evidence_coverage_percent: float = 0.0,
    maximum_blocked_count: int = 0,
    maximum_superseded_count: int = 0,
    maximum_event_count: int = 400_000,
    require_audit_acceptance: bool = True,
) -> ModuleWorkbenchExecutionPolicy:
    """Build an immutable execution policy with explicit thresholds."""

    body = {
        "policy_id": policy_id,
        "minimum_completion_percent": minimum_completion_percent,
        "minimum_evidence_coverage_percent": minimum_evidence_coverage_percent,
        "maximum_blocked_count": maximum_blocked_count,
        "maximum_superseded_count": maximum_superseded_count,
        "maximum_event_count": maximum_event_count,
        "require_audit_acceptance": require_audit_acceptance,
    }
    provisional = ModuleWorkbenchExecutionPolicy(**body, content_address="pending")
    return ModuleWorkbenchExecutionPolicy(
        **body,
        content_address=address_module_workbench_execution_policy(provisional),
    )


def default_module_workbench_execution_policy() -> ModuleWorkbenchExecutionPolicy:
    """Return the balanced planning policy."""

    return build_module_workbench_execution_policy()


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPolicyCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPolicyCheck(**body, content_address="pending")
    return ModuleWorkbenchExecutionPolicyCheck(
        **body,
        content_address=address_module_workbench_execution_policy_check(provisional),
    )


def evaluate_module_workbench_execution_policy(
    ledger: ModuleWorkbenchExecutionLedger,
    policy: ModuleWorkbenchExecutionPolicy | None = None,
    audit: ModuleWorkbenchExecutionAudit | None = None,
) -> ModuleWorkbenchExecutionPolicyGate:
    """Evaluate progress, exception, event-budget, and audit thresholds."""

    if not isinstance(ledger, ModuleWorkbenchExecutionLedger):
        raise ValidationError("execution policy requires a typed ledger")
    selected_policy = policy or default_module_workbench_execution_policy()
    if not isinstance(selected_policy, ModuleWorkbenchExecutionPolicy):
        raise ValidationError("execution policy must be typed")
    selected_audit = audit or audit_module_workbench_execution(ledger)
    if not isinstance(selected_audit, ModuleWorkbenchExecutionAudit):
        raise ValidationError("execution policy audit must be typed")
    checks = tuple(
        sorted(
            (
                _check(
                    "accepted-input",
                    ledger.accepted,
                    ledger.accepted,
                    True,
                    "the source report and selected portfolio were accepted",
                ),
                _check(
                    "audit-acceptance",
                    selected_audit.accepted if selected_policy.require_audit_acceptance else True,
                    selected_audit.accepted,
                    True if selected_policy.require_audit_acceptance else "not-required",
                    "independent execution invariants satisfy the configured policy",
                ),
                _check(
                    "blocked-count",
                    ledger.blocked_count <= selected_policy.maximum_blocked_count,
                    ledger.blocked_count,
                    f"<={selected_policy.maximum_blocked_count}",
                    "blocked implementation tasks remain within the configured limit",
                ),
                _check(
                    "completion-percent",
                    ledger.completion_percent >= selected_policy.minimum_completion_percent,
                    ledger.completion_percent,
                    f">={selected_policy.minimum_completion_percent}",
                    "aggregate task completion reaches the configured floor",
                ),
                _check(
                    "evidence-coverage",
                    ledger.evidence_coverage_percent
                    >= selected_policy.minimum_evidence_coverage_percent,
                    ledger.evidence_coverage_percent,
                    f">={selected_policy.minimum_evidence_coverage_percent}",
                    "declared execution evidence reaches the configured floor",
                ),
                _check(
                    "event-budget",
                    len(ledger.events) <= selected_policy.maximum_event_count,
                    len(ledger.events),
                    f"<={selected_policy.maximum_event_count}",
                    "append-only event history remains bounded",
                ),
                _check(
                    "superseded-count",
                    ledger.superseded_count <= selected_policy.maximum_superseded_count,
                    ledger.superseded_count,
                    f"<={selected_policy.maximum_superseded_count}",
                    "superseded tasks remain within the configured limit",
                ),
            ),
            key=lambda item: item.check_id,
        )
    )
    body = {
        "ledger_address": ledger.content_address,
        "audit_address": selected_audit.content_address,
        "policy_address": selected_policy.content_address,
        "checks": checks,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchExecutionPolicyGate(**body, content_address="pending")
    return ModuleWorkbenchExecutionPolicyGate(
        **body,
        content_address=address_module_workbench_execution_policy_gate(provisional),
    )


def verify_module_workbench_execution_policy(
    value: ModuleWorkbenchExecutionPolicy,
) -> ModuleWorkbenchExecutionPolicy:
    """Verify a policy address."""

    if not isinstance(value, ModuleWorkbenchExecutionPolicy):
        raise ValidationError("execution policy verification requires a typed policy")
    if address_module_workbench_execution_policy(value) != value.content_address:
        raise ValidationError("execution policy address mismatch")
    return value


def verify_module_workbench_execution_policy_gate(
    value: ModuleWorkbenchExecutionPolicyGate,
) -> ModuleWorkbenchExecutionPolicyGate:
    """Verify nested policy checks and aggregate address."""

    if not isinstance(value, ModuleWorkbenchExecutionPolicyGate):
        raise ValidationError("execution policy gate verification requires a typed gate")
    for check in value.checks:
        if address_module_workbench_execution_policy_check(check) != check.content_address:
            raise ValidationError(f"execution policy check address mismatch: {check.check_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-execution-policy-gate") != value.content_address:
        raise ValidationError("execution policy gate address mismatch")
    return value


def query_module_workbench_execution_policy(
    value: ModuleWorkbenchExecutionPolicyGate,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_POLICY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded policy-check page."""

    if not isinstance(value, ModuleWorkbenchExecutionPolicyGate):
        raise ValidationError("execution policy query requires a typed gate")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_POLICY_MAX_LIMIT:
        raise ValidationError("execution policy paging is invalid")
    rows = [item.to_dict() for item in value.checks]
    if passed is not None:
        rows = [item for item in rows if item.get("passed") is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "gate_address": value.content_address,
        "query": {"passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-execution-policy-query")}


def module_workbench_execution_policy_json(
    value: ModuleWorkbenchExecutionPolicyGate,
) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_policy_csv(
    value: ModuleWorkbenchExecutionPolicyGate,
) -> str:
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        writer.writerow(
            {
                "check_id": check.check_id,
                "passed": check.passed,
                "observed": canonical_json(check.observed),
                "required": canonical_json(check.required),
                "detail": check.detail,
                "content_address": check.content_address,
            }
        )
    return output.getvalue()


def module_workbench_execution_policy_summary(
    value: ModuleWorkbenchExecutionPolicyGate,
) -> dict[str, Any]:
    return value.to_dict(include_checks=False)


def module_workbench_execution_policy_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_EXECUTION_POLICY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_POLICY_BOUNDARY,
        "thresholds": [
            "minimum_completion_percent",
            "minimum_evidence_coverage_percent",
            "maximum_blocked_count",
            "maximum_superseded_count",
            "maximum_event_count",
            "require_audit_acceptance",
        ],
        "resources": ["checks", "summary"],
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_policy_capabilities() -> dict[str, Any]:
    operations = (
        "build_policy",
        "evaluate_completion_threshold",
        "evaluate_evidence_threshold",
        "evaluate_blocked_threshold",
        "evaluate_superseded_threshold",
        "evaluate_event_budget",
        "require_independent_audit",
        "query_checks",
        "summarize_gate",
        "export_json",
        "export_csv",
        "verify_policy_address",
        "verify_gate_address",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_POLICY_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "explicit_thresholds": True,
    }


__all__ = [
    "build_module_workbench_execution_policy",
    "default_module_workbench_execution_policy",
    "evaluate_module_workbench_execution_policy",
    "module_workbench_execution_policy_capabilities",
    "module_workbench_execution_policy_csv",
    "module_workbench_execution_policy_json",
    "module_workbench_execution_policy_schema",
    "module_workbench_execution_policy_summary",
    "query_module_workbench_execution_policy",
    "verify_module_workbench_execution_policy",
    "verify_module_workbench_execution_policy_gate",
]
