"""Configurable quality policy evaluation for certification release controls."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_quality_contracts import ModuleCertificationQualityReport
from .module_certification_quality_policy_contracts import (
    MODULE_CERTIFICATION_QUALITY_POLICY_BOUNDARY,
    MODULE_CERTIFICATION_QUALITY_POLICY_MAX_LIMIT,
    MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
    ModuleCertificationQualityGate,
    ModuleCertificationQualityPolicy,
    ModuleCertificationQualityPolicyCheck,
    address_module_certification_quality_policy,
    address_module_certification_quality_policy_check,
)
from .serialization import canonical_json, content_hash, jsonable


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def build_module_certification_quality_policy(
    *,
    minimum_evidence_coverage_percent: float = 100.0,
    minimum_check_pass_percent: float = 100.0,
    minimum_family_score: float = 0.8,
    require_no_blockers: bool = True,
    require_all_modules_certified: bool = True,
    require_ready: bool = True,
) -> ModuleCertificationQualityPolicy:
    """Build an immutable threshold policy with no repository access."""

    body = {
        "minimum_evidence_coverage_percent": minimum_evidence_coverage_percent,
        "minimum_check_pass_percent": minimum_check_pass_percent,
        "minimum_family_score": minimum_family_score,
        "require_no_blockers": require_no_blockers,
        "require_all_modules_certified": require_all_modules_certified,
        "require_ready": require_ready,
    }
    return ModuleCertificationQualityPolicy(
        **body,
        content_address=_address(body, "module-certification-quality-policy"),
    )


def default_module_certification_quality_policy() -> ModuleCertificationQualityPolicy:
    """Return the strict policy used by release-oriented CI."""

    return build_module_certification_quality_policy()


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleCertificationQualityPolicyCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleCertificationQualityPolicyCheck(
        **body,
        content_address=_address(body, "module-certification-quality-policy-check"),
    )


def _policy_checks(
    value: ModuleCertificationQualityReport,
    policy: ModuleCertificationQualityPolicy,
) -> tuple[ModuleCertificationQualityPolicyCheck, ...]:
    checks: list[ModuleCertificationQualityPolicyCheck] = [
        _check(
            "evidence-coverage",
            value.evidence_coverage_percent >= policy.minimum_evidence_coverage_percent,
            value.evidence_coverage_percent,
            policy.minimum_evidence_coverage_percent,
            "non-source evidence coverage meets the configured minimum",
        ),
        _check(
            "no-blockers",
            not policy.require_no_blockers or not value.blocker_modules,
            len(value.blocker_modules),
            0 if policy.require_no_blockers else "not_required",
            "blocking module requirement is satisfied",
        ),
        _check(
            "all-modules-certified",
            not policy.require_all_modules_certified
            or all(item.certified_count == item.module_count for item in value.family_coverage),
            value.readiness.value,
            "all_certified" if policy.require_all_modules_certified else "not_required",
            "all module rows satisfy the certified state requirement",
        ),
        _check(
            "readiness",
            not policy.require_ready or value.readiness.value == "ready",
            value.readiness.value,
            "ready" if policy.require_ready else "not_required",
            "quality readiness meets the configured release requirement",
        ),
    ]
    for measure in value.check_coverage:
        checks.append(
            _check(
                f"check-pass-rate:{measure.kind}",
                measure.pass_percent >= policy.minimum_check_pass_percent,
                measure.pass_percent,
                policy.minimum_check_pass_percent,
                f"{measure.kind} check pass rate meets the configured minimum",
            )
        )
    for measure in value.family_coverage:
        checks.append(
            _check(
                f"family-score:{measure.family}",
                measure.overall_score >= policy.minimum_family_score,
                measure.overall_score,
                policy.minimum_family_score,
                f"{measure.family} family score meets the configured minimum",
            )
        )
    return tuple(sorted(checks, key=lambda item: item.check_id))


def evaluate_module_certification_quality_policy(
    value: ModuleCertificationQualityReport,
    policy: ModuleCertificationQualityPolicy | None = None,
) -> ModuleCertificationQualityGate:
    """Evaluate policy thresholds against a static quality report."""

    if not isinstance(value, ModuleCertificationQualityReport):
        raise ValidationError("quality policy requires a typed quality report")
    selected = policy or default_module_certification_quality_policy()
    if not isinstance(selected, ModuleCertificationQualityPolicy):
        raise ValidationError("quality policy is invalid")
    checks = _policy_checks(value, selected)
    passed = sum(item.passed for item in checks)
    body = {
        "quality_address": value.content_address,
        "policy": selected,
        "checks": checks,
        "passed_count": passed,
        "failed_count": len(checks) - passed,
        "accepted": all(item.passed for item in checks),
    }
    return ModuleCertificationQualityGate(
        **body,
        content_address=_address(body, "module-certification-quality-gate"),
    )


def verify_module_certification_quality_policy(
    value: ModuleCertificationQualityPolicy,
) -> ModuleCertificationQualityPolicy:
    """Verify a policy address without reading the quality report."""

    if not isinstance(value, ModuleCertificationQualityPolicy):
        raise ValidationError("quality policy verification requires a typed policy")
    if address_module_certification_quality_policy(value) != value.content_address:
        raise ValidationError("quality policy address mismatch")
    return value


def verify_module_certification_quality_gate(
    value: ModuleCertificationQualityGate,
) -> ModuleCertificationQualityGate:
    """Verify policy and check addresses without source access."""

    if not isinstance(value, ModuleCertificationQualityGate):
        raise ValidationError("quality gate verification requires a typed gate")
    verify_module_certification_quality_policy(value.policy)
    for check in value.checks:
        if address_module_certification_quality_policy_check(check) != check.content_address:
            raise ValidationError(f"quality gate check address mismatch: {check.check_id}")
    body = {
        "quality_address": value.quality_address,
        "policy": value.policy,
        "checks": value.checks,
        "passed_count": value.passed_count,
        "failed_count": value.failed_count,
        "accepted": value.accepted,
    }
    if _address(body, "module-certification-quality-gate") != value.content_address:
        raise ValidationError("quality gate address mismatch")
    return value


def query_module_certification_quality_policy(
    value: ModuleCertificationQualityGate,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded page over policy decisions."""

    if not isinstance(value, ModuleCertificationQualityGate):
        raise ValidationError("quality policy query requires a typed gate")
    if offset < 0 or limit < 1 or limit > MODULE_CERTIFICATION_QUALITY_POLICY_MAX_LIMIT:
        raise ValidationError("quality policy pagination is invalid")
    rows = list(value.checks)
    if passed is not None:
        rows = [item for item in rows if item.passed is passed]
    if text:
        rows = [
            item for item in rows if text.casefold() in canonical_json(item.to_dict()).casefold()
        ]
    body = {
        "version": MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
        "resource": "checks",
        "query": {"passed": passed, "text": text, "offset": offset, "limit": limit},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": tuple(jsonable(item) for item in rows[offset : offset + limit]),
        "quality_address": value.quality_address,
        "policy_address": value.policy.content_address,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-quality-policy-query")}


def module_certification_quality_policy_json(value: ModuleCertificationQualityGate) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_certification_quality_policy_csv(value: ModuleCertificationQualityGate) -> str:
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def module_certification_quality_policy_failures(
    value: ModuleCertificationQualityGate,
) -> tuple[str, ...]:
    """Return failed policy IDs in stable review order."""

    if not isinstance(value, ModuleCertificationQualityGate):
        raise ValidationError("quality policy failures require a typed gate")
    return tuple(sorted(item.check_id for item in value.checks if not item.passed))


def module_certification_quality_policy_summary(
    value: ModuleCertificationQualityGate,
) -> dict[str, Any]:
    """Return a compact, addressable decision summary without check rows."""

    if not isinstance(value, ModuleCertificationQualityGate):
        raise ValidationError("quality policy summary requires a typed gate")
    body = {
        "version": MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
        "boundary": MODULE_CERTIFICATION_QUALITY_POLICY_BOUNDARY,
        "quality_address": value.quality_address,
        "policy_address": value.policy.content_address,
        "check_count": value.check_count,
        "passed_count": value.passed_count,
        "failed_count": value.failed_count,
        "failed_check_ids": module_certification_quality_policy_failures(value),
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-quality-policy-summary")}


def render_module_certification_quality_policy_markdown(
    value: ModuleCertificationQualityGate,
) -> str:
    """Render a reviewer-facing policy decision with observed thresholds."""

    if not isinstance(value, ModuleCertificationQualityGate):
        raise ValidationError("quality policy markdown requires a typed gate")
    policy = value.policy
    lines = [
        "# Module certification quality policy",
        "",
        f"- Accepted: **{str(value.accepted).lower()}**",
        f"- Checks passed: **{value.passed_count}/{value.check_count}**",
        f"- Quality address: `{value.quality_address}`",
        "",
        "| Policy control | Required |",
        "| --- | ---: |",
        f"| Evidence coverage | {policy.minimum_evidence_coverage_percent:.2f}% |",
        f"| Check pass rate | {policy.minimum_check_pass_percent:.2f}% |",
        f"| Family score | {policy.minimum_family_score:.4f} |",
        f"| No blockers | {str(policy.require_no_blockers).lower()} |",
        f"| All modules certified | {str(policy.require_all_modules_certified).lower()} |",
        f"| Ready status | {str(policy.require_ready).lower()} |",
        "",
        "| Decision | Passed | Observed | Required |",
        "| --- | --- | --- | --- |",
    ]
    for item in value.checks:
        lines.append(
            f"| `{item.check_id}` | {str(item.passed).lower()} | "
            f"{item.observed} | {item.required} |"
        )
    return "\n".join(lines) + "\n"


def compare_module_certification_quality_policies(
    left: ModuleCertificationQualityPolicy,
    right: ModuleCertificationQualityPolicy,
) -> dict[str, Any]:
    """Compare policy thresholds without applying either policy to source."""

    if not isinstance(left, ModuleCertificationQualityPolicy) or not isinstance(
        right, ModuleCertificationQualityPolicy
    ):
        raise ValidationError("quality policy comparison requires typed policies")
    fields = (
        "minimum_evidence_coverage_percent",
        "minimum_check_pass_percent",
        "minimum_family_score",
        "require_no_blockers",
        "require_all_modules_certified",
        "require_ready",
    )
    changed = tuple(field for field in fields if getattr(left, field) != getattr(right, field))
    body = {
        "version": MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
        "resource": "policies",
        "left_policy_address": left.content_address,
        "right_policy_address": right.content_address,
        "changed_fields": changed,
        "left_values": {field: getattr(left, field) for field in fields},
        "right_values": {field: getattr(right, field) for field in fields},
    }
    return body | {"content_address": _address(body, "module-certification-quality-policy-diff")}


def compare_module_certification_quality_gates(
    left: ModuleCertificationQualityGate,
    right: ModuleCertificationQualityGate,
) -> dict[str, Any]:
    """Compare two policy decisions by check identity and pass state."""

    if not isinstance(left, ModuleCertificationQualityGate) or not isinstance(
        right, ModuleCertificationQualityGate
    ):
        raise ValidationError("quality gate comparison requires typed gates")
    left_checks = {item.check_id: item.passed for item in left.checks}
    right_checks = {item.check_id: item.passed for item in right.checks}
    changed = tuple(
        sorted(
            check_id
            for check_id in set(left_checks) | set(right_checks)
            if left_checks.get(check_id) != right_checks.get(check_id)
        )
    )
    body = {
        "version": MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
        "resource": "gates",
        "left_gate_address": left.content_address,
        "right_gate_address": right.content_address,
        "left_policy_address": left.policy.content_address,
        "right_policy_address": right.policy.content_address,
        "changed_check_ids": changed,
        "left_accepted": left.accepted,
        "right_accepted": right.accepted,
        "accepted_changed": left.accepted != right.accepted,
        "left_failed_count": left.failed_count,
        "right_failed_count": right.failed_count,
    }
    return body | {"content_address": _address(body, "module-certification-quality-gate-diff")}


def module_certification_quality_policy_schema() -> dict[str, Any]:
    return {
        "version": MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
        "boundary": MODULE_CERTIFICATION_QUALITY_POLICY_BOUNDARY,
        "policy_fields": [
            "minimum_evidence_coverage_percent",
            "minimum_check_pass_percent",
            "minimum_family_score",
            "require_no_blockers",
            "require_all_modules_certified",
            "require_ready",
            "content_address",
        ],
        "check_fields": ["check_id", "passed", "observed", "required", "detail", "content_address"],
        "gate_fields": [
            "quality_address",
            "policy",
            "checks",
            "passed_count",
            "failed_count",
            "accepted",
            "content_address",
        ],
        "query_filters": ["passed", "text"],
        "policy": "all configured checks must pass for an accepted gate",
    }


def module_certification_quality_policy_capabilities() -> dict[str, Any]:
    operations = (
        "build_quality_policy",
        "use_default_quality_policy",
        "check_evidence_threshold",
        "check_blocker_threshold",
        "check_all_certified_threshold",
        "check_readiness_threshold",
        "check_per_kind_pass_rates",
        "check_per_family_scores",
        "evaluate_quality_gate",
        "query_policy_checks",
        "export_policy_csv",
        "verify_policy_address",
        "verify_gate_addresses",
    )
    return {
        "version": MODULE_CERTIFICATION_QUALITY_POLICY_VERSION,
        "boundary": MODULE_CERTIFICATION_QUALITY_POLICY_BOUNDARY,
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
        "source_execution": False,
        "customizable": True,
    }


__all__ = [
    "build_module_certification_quality_policy",
    "compare_module_certification_quality_gates",
    "compare_module_certification_quality_policies",
    "default_module_certification_quality_policy",
    "evaluate_module_certification_quality_policy",
    "module_certification_quality_policy_capabilities",
    "module_certification_quality_policy_csv",
    "module_certification_quality_policy_json",
    "module_certification_quality_policy_schema",
    "query_module_certification_quality_policy",
    "verify_module_certification_quality_gate",
    "verify_module_certification_quality_policy",
]
