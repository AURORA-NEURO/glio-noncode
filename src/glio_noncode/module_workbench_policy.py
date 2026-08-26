"""Evaluate configurable release thresholds over module workbench depth data."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench import module_workbench_schema
from .module_workbench_contracts import (
    ModuleWorkbenchReport,
)
from .module_workbench_policy_contracts import (
    MODULE_WORKBENCH_POLICY_DEFAULT_LIMIT,
    MODULE_WORKBENCH_POLICY_MAX_LIMIT,
    MODULE_WORKBENCH_POLICY_VERSION,
    ModuleWorkbenchGate,
    ModuleWorkbenchPolicy,
    ModuleWorkbenchPolicyCheck,
    address_module_workbench_policy,
    address_module_workbench_policy_check,
)
from .serialization import canonical_json, content_hash, jsonable


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def build_module_workbench_policy(
    *,
    policy_id: str = "module-workbench-default",
    minimum_overall_score: float = 0.70,
    minimum_depth_percent: float = 70.0,
    maximum_blocked_count: int = 0,
    maximum_high_risk_count: int = 500,
    minimum_family_score: float = 0.45,
    required_dimensions: tuple[str, ...] = (
        "connectivity",
        "dependency_resolution",
        "evidence",
        "implementation_scale",
        "parse",
        "public_contract",
        "test_references",
    ),
    minimum_test_references: int = 0,
    minimum_evidence_count: int = 1,
) -> ModuleWorkbenchPolicy:
    """Build an immutable workbench policy with stable threshold identity."""

    body = {
        "policy_id": policy_id,
        "minimum_overall_score": minimum_overall_score,
        "minimum_depth_percent": minimum_depth_percent,
        "maximum_blocked_count": maximum_blocked_count,
        "maximum_high_risk_count": maximum_high_risk_count,
        "minimum_family_score": minimum_family_score,
        "required_dimensions": tuple(sorted(set(required_dimensions))),
        "minimum_test_references": minimum_test_references,
        "minimum_evidence_count": minimum_evidence_count,
    }
    provisional = ModuleWorkbenchPolicy(**body, content_address="pending")
    return ModuleWorkbenchPolicy(
        **body,
        content_address=address_module_workbench_policy(provisional),
    )


def default_module_workbench_policy() -> ModuleWorkbenchPolicy:
    """Return the repository's balanced default depth policy."""

    return build_module_workbench_policy()


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchPolicyCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchPolicyCheck(**body, content_address="pending")
    return ModuleWorkbenchPolicyCheck(
        **body,
        content_address=address_module_workbench_policy_check(provisional),
    )


def evaluate_module_workbench_policy(
    report: ModuleWorkbenchReport,
    policy: ModuleWorkbenchPolicy | None = None,
) -> ModuleWorkbenchGate:
    """Evaluate project, family, dimension, and minimum-evidence thresholds."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("workbench policy requires a typed report")
    selected = policy or default_module_workbench_policy()
    if not isinstance(selected, ModuleWorkbenchPolicy):
        raise ValidationError("workbench policy must be typed")
    checks = (
        _check(
            "accepted-inputs",
            report.accepted,
            report.accepted,
            True,
            "inventory, certification, lineage, and quality inputs are accepted",
        ),
        _check(
            "blocked-count",
            report.blocked_count <= selected.maximum_blocked_count,
            report.blocked_count,
            f"<={selected.maximum_blocked_count}",
            "blocked modules remain within the configured limit",
        ),
        _check(
            "depth-percent",
            report.depth_percent >= selected.minimum_depth_percent,
            report.depth_percent,
            f">={selected.minimum_depth_percent}",
            "deep or comprehensive module percentage reaches the configured floor",
        ),
        _check(
            "dimension-registry",
            all(
                all(dimension.name in selected.required_dimensions for dimension in item.dimensions)
                for item in report.assessments
            ),
            sorted(
                {dimension.name for item in report.assessments for dimension in item.dimensions}
            ),
            list(selected.required_dimensions),
            "every assessment exposes only registered depth dimensions",
        ),
        _check(
            "evidence-count",
            all(
                item.evidence_count >= selected.minimum_evidence_count
                for item in report.assessments
            ),
            min((item.evidence_count for item in report.assessments), default=0),
            f">={selected.minimum_evidence_count}",
            "every module has the minimum linked evidence count",
        ),
        _check(
            "family-score",
            all(item.average_score >= selected.minimum_family_score for item in report.families),
            min((item.average_score for item in report.families), default=0.0),
            f">={selected.minimum_family_score}",
            "every family reaches the configured average depth floor",
        ),
        _check(
            "high-risk-count",
            report.high_risk_count <= selected.maximum_high_risk_count,
            report.high_risk_count,
            f"<={selected.maximum_high_risk_count}",
            "high and blocker risk modules remain within the configured limit",
        ),
        _check(
            "minimum-test-references",
            all(
                item.test_reference_count >= selected.minimum_test_references
                for item in report.assessments
            ),
            min((item.test_reference_count for item in report.assessments), default=0),
            f">={selected.minimum_test_references}",
            "every module reaches the configured test-reference floor",
        ),
        _check(
            "overall-score",
            report.overall_score >= selected.minimum_overall_score,
            report.overall_score,
            f">={selected.minimum_overall_score}",
            "aggregate module depth reaches the configured score floor",
        ),
    )
    body = {
        "report_address": report.content_address,
        "policy_address": selected.content_address,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchGate(**body, content_address="pending")
    gate_body = provisional.to_dict()
    gate_body.pop("content_address", None)
    return ModuleWorkbenchGate(
        **body,
        content_address=_address(gate_body, "module-workbench-gate"),
    )


def verify_module_workbench_policy(policy: ModuleWorkbenchPolicy) -> ModuleWorkbenchPolicy:
    """Verify a policy's immutable content address."""

    if not isinstance(policy, ModuleWorkbenchPolicy):
        raise ValidationError("workbench policy verification requires a typed policy")
    if address_module_workbench_policy(policy) != policy.content_address:
        raise ValidationError("module workbench policy address mismatch")
    return policy


def verify_module_workbench_gate(gate: ModuleWorkbenchGate) -> ModuleWorkbenchGate:
    """Verify check addresses and the aggregate gate address."""

    if not isinstance(gate, ModuleWorkbenchGate):
        raise ValidationError("workbench gate verification requires a typed gate")
    for check in gate.checks:
        if address_module_workbench_policy_check(check) != check.content_address:
            raise ValidationError(f"workbench policy check address mismatch: {check.check_id}")
    body = gate.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-gate") != gate.content_address:
        raise ValidationError("module workbench gate address mismatch")
    return gate


def _query_rows(gate: ModuleWorkbenchGate, resource: str) -> list[dict[str, Any]]:
    if resource == "checks":
        return [item.to_dict() for item in gate.checks]
    if resource == "summary":
        return [gate.to_dict(include_checks=False)]
    raise ValidationError("workbench policy resource must be checks or summary")


def query_module_workbench_policy(
    gate: ModuleWorkbenchGate,
    *,
    resource: str = "checks",
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_POLICY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded gate-check page."""

    if not isinstance(gate, ModuleWorkbenchGate):
        raise ValidationError("workbench policy query requires a typed gate")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_POLICY_MAX_LIMIT:
        raise ValidationError("workbench policy paging is invalid")
    rows = _query_rows(gate, resource)
    if passed is not None:
        rows = [item for item in rows if item.get("passed") is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "gate_address": gate.content_address,
        "query": {"resource": resource, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": gate.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-policy-query")}


def module_workbench_policy_summary(gate: ModuleWorkbenchGate) -> dict[str, Any]:
    """Return a compact threshold decision for dashboards."""

    if not isinstance(gate, ModuleWorkbenchGate):
        raise ValidationError("workbench policy summary requires a typed gate")
    return jsonable(gate.to_dict(include_checks=False))


def module_workbench_policy_csv(gate: ModuleWorkbenchGate) -> str:
    fields = (
        "check_id",
        "passed",
        "observed",
        "required",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in gate.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def module_workbench_policy_json(gate: ModuleWorkbenchGate) -> str:
    return canonical_json(gate.to_dict()) + "\n"


def render_module_workbench_policy_markdown(gate: ModuleWorkbenchGate) -> str:
    """Render the gate as a human-readable release decision."""

    lines = [
        "# Module workbench policy",
        "",
        f"- Gate address: `{gate.content_address}`",
        f"- Checks: **{len(gate.checks)}**",
        f"- Passed / failed: **{gate.passed_count} / {gate.failed_count}**",
        f"- Accepted: **{str(gate.accepted).lower()}**",
        "",
        "| Check | Passed | Observed | Required | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in gate.checks:
        lines.append(
            f"| `{item.check_id}` | {str(item.passed).lower()} | `{item.observed}` | "
            f"`{item.required}` | {item.detail} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_policy_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_POLICY_VERSION,
        "boundary": "public_aggregate_module_workbench_policy",
        "resources": ["checks", "summary"],
        "thresholds": [
            "minimum_overall_score",
            "minimum_depth_percent",
            "maximum_blocked_count",
            "maximum_high_risk_count",
            "minimum_family_score",
            "required_dimensions",
            "minimum_test_references",
            "minimum_evidence_count",
        ],
        "depends_on": module_workbench_schema()["boundary"],
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_policy_capabilities() -> dict[str, Any]:
    operations = (
        "build_policy",
        "evaluate_overall_score",
        "evaluate_depth_percent",
        "evaluate_blocked_count",
        "evaluate_high_risk_count",
        "evaluate_family_score",
        "evaluate_dimension_registry",
        "evaluate_test_references",
        "evaluate_evidence_count",
        "query_checks",
        "summarize_gate",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_POLICY_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_policy",
    "default_module_workbench_policy",
    "evaluate_module_workbench_policy",
    "module_workbench_policy_capabilities",
    "module_workbench_policy_csv",
    "module_workbench_policy_json",
    "module_workbench_policy_schema",
    "module_workbench_policy_summary",
    "query_module_workbench_policy",
    "render_module_workbench_policy_markdown",
    "verify_module_workbench_gate",
    "verify_module_workbench_policy",
]
