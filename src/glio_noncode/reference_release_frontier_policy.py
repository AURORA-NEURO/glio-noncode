"""Deny-by-default policy receipts for reference release operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_public_data import (
    ReferenceReleaseFixture,
    ReferenceReleaseOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleasePolicyRule:
    """One named policy condition and its failure behavior."""

    rule_id: str
    operation: ReferenceReleaseOperation | None
    title: str
    severity: str
    required: bool
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "title", "severity", "rationale", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.severity not in {"info", "review", "blocking"}:
            raise ValueError("policy severity must be info, review, or blocking")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleasePolicyDecision:
    """Policy result for one execution receipt."""

    record_id: str
    operation: ReferenceReleaseOperation
    allowed: bool
    rule_results: tuple[tuple[str, bool], ...]
    failed_rule_ids: tuple[str, ...]
    action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleasePolicyReport:
    """Aggregate policy evaluation with explicit rule accounting."""

    fixture_id: str
    rules: tuple[ReferenceReleasePolicyRule, ...]
    decisions: tuple[ReferenceReleasePolicyDecision, ...]
    checks: tuple[tuple[str, bool, str], ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check_id for check_id, passed, _ in self.checks if not passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _rule(
    rule_id: str,
    operation: ReferenceReleaseOperation | None,
    title: str,
    severity: str,
    required: bool,
    rationale: str,
) -> ReferenceReleasePolicyRule:
    body = {
        "rule_id": rule_id,
        "operation": operation,
        "title": title,
        "severity": severity,
        "required": required,
        "rationale": rationale,
    }
    return ReferenceReleasePolicyRule(
        **body, content_address=content_hash(body, prefix="release-policy-rule")
    )


def default_reference_release_policy_rules() -> tuple[ReferenceReleasePolicyRule, ...]:
    """Return the complete set of source, context, output, and release rules."""

    return (
        _rule(
            "RRP-001",
            None,
            "public aggregate boundary",
            "blocking",
            True,
            "Only aggregate metadata and public receipts enter the package.",
        ),
        _rule(
            "RRP-002",
            None,
            "exact context required",
            "blocking",
            True,
            "Assembly, disease, age, specimen, territory, and phase remain exact.",
        ),
        _rule(
            "RRP-003",
            ReferenceReleaseOperation.PROVENANCE_CHECK,
            "URI and checksum visible",
            "blocking",
            True,
            "A source cannot pass when its location or observed checksum is missing.",
        ),
        _rule(
            "RRP-004",
            ReferenceReleaseOperation.PROVENANCE_CHECK,
            "license required",
            "blocking",
            True,
            "Missing license metadata is retained as review.",
        ),
        _rule(
            "RRP-005",
            ReferenceReleaseOperation.ANNOTATION_DRIFT,
            "drift remains descriptive",
            "review",
            True,
            "Field changes are not converted into biological or clinical claims.",
        ),
        _rule(
            "RRP-006",
            ReferenceReleaseOperation.ANNOTATION_DRIFT,
            "ignored receipt fields stay ignored",
            "info",
            True,
            "Retrieval metadata does not create false drift.",
        ),
        _rule(
            "RRP-007",
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "available rows only",
            "blocking",
            True,
            "Unavailable reference metadata cannot be published.",
        ),
        _rule(
            "RRP-008",
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "bundle context exact",
            "blocking",
            True,
            "Foreign context is rejected before sorting or release.",
        ),
        _rule(
            "RRP-009",
            ReferenceReleaseOperation.REFERENCE_BUNDLE,
            "bundle is content addressed",
            "review",
            True,
            "A bundle must carry a reproducible address.",
        ),
        _rule(
            "RRP-010",
            ReferenceReleaseOperation.RELEASE_GATE,
            "required checks explicit",
            "blocking",
            True,
            "Missing or false required checks block release.",
        ),
        _rule(
            "RRP-011",
            ReferenceReleaseOperation.RELEASE_GATE,
            "failed checks itemized",
            "review",
            True,
            "Every failed check is retained in the decision.",
        ),
        _rule(
            "RRP-012",
            None,
            "no hidden mutation",
            "blocking",
            True,
            "The package only emits deterministic metadata and receipts.",
        ),
    )


def _decision(
    record_id: str,
    operation: ReferenceReleaseOperation,
    execution: Any,
    rules: tuple[ReferenceReleasePolicyRule, ...],
) -> ReferenceReleasePolicyDecision:
    relevant = tuple(
        rule for rule in rules if rule.operation is None or rule.operation is operation
    )
    results: list[tuple[str, bool]] = []
    for rule in relevant:
        passed = True
        if rule.rule_id == "RRP-003":
            passed = (
                execution.state == "accepted"
                or "missing_source_uri" not in execution.issue_codes
                and "checksum_unverified" not in execution.issue_codes
            )
        elif rule.rule_id == "RRP-004":
            passed = "missing_license" not in execution.issue_codes
        elif rule.rule_id == "RRP-007":
            passed = "bundle_unavailable" not in execution.issue_codes
        elif rule.rule_id == "RRP-008":
            passed = "bundle_context_mismatch" not in execution.issue_codes
        elif rule.rule_id == "RRP-009":
            passed = execution.state == "published" or "bundle" not in execution.operation.value
        elif rule.rule_id == "RRP-010":
            passed = "release_check_failed" not in execution.issue_codes
        elif rule.rule_id == "RRP-011":
            passed = execution.state != "blocked" or bool(execution.issue_codes)
        results.append((rule.rule_id, passed))
    failed = tuple(rule_id for rule_id, passed in results if not passed)
    allowed = not failed
    return ReferenceReleasePolicyDecision(
        record_id,
        operation,
        allowed,
        tuple(results),
        failed,
        "publish" if allowed else "review",
        content_hash(
            {
                "record_id": record_id,
                "operation": operation,
                "allowed": allowed,
                "rule_results": tuple(results),
                "failed_rule_ids": failed,
            },
            prefix="release-policy-decision",
        ),
    )


def evaluate_reference_release_policy(
    fixture: ReferenceReleaseFixture, evaluation: ReferenceReleaseEvaluation
) -> ReferenceReleasePolicyReport:
    """Evaluate every execution against the declared release policy."""

    rules = default_reference_release_policy_rules()
    decisions = tuple(
        _decision(item.record_id, item.operation, item, rules) for item in evaluation.executions
    )
    checks = (
        ("rule-count", len(rules) == 12, "twelve named policy rules exist"),
        (
            "execution-count",
            len(decisions) == len(fixture.records),
            "every record receives a policy decision",
        ),
        (
            "decision-addresses",
            all(item.content_address.startswith("release-policy-decision:") for item in decisions),
            "decisions are addressed",
        ),
        (
            "rule-addresses",
            all(item.content_address.startswith("release-policy-rule:") for item in rules),
            "rules are addressed",
        ),
        (
            "failure-detail",
            all(not item.failed_rule_ids or item.action == "review" for item in decisions),
            "failed rules route to review",
        ),
        (
            "operation-coverage",
            {item.operation for item in decisions} == set(ReferenceReleaseOperation),
            "all operations receive policy coverage",
        ),
        (
            "context-boundary",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "policy is bound to aggregate evidence",
        ),
        (
            "deterministic-order",
            tuple(item.record_id for item in decisions)
            == tuple(item.record_id for item in evaluation.executions),
            "decision order follows evaluation order",
        ),
        (
            "positive-acceptance",
            all(item.allowed for item in decisions if item.record_id.endswith("POS-001")),
            "positive records are publishable when checks pass",
        ),
        (
            "control-visibility",
            any(not item.allowed for item in decisions if "CTRL" in item.record_id),
            "control failures remain visible",
        ),
        ("required-rules", all(item.required for item in rules), "all current rules are required"),
        (
            "no-raw-fields",
            all("payload" not in item.to_dict() for item in decisions),
            "decisions contain no raw input payload",
        ),
    )
    accepted = all(passed for _, passed, _ in checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "rules": rules,
        "decisions": decisions,
        "checks": checks,
        "accepted": accepted,
    }
    return ReferenceReleasePolicyReport(
        **body, content_address=content_hash(body, prefix="release-policy-report")
    )


def verify_reference_release_policy(report: ReferenceReleasePolicyReport) -> tuple[str, ...]:
    """Return policy integrity failures."""

    failures = list(report.failed_check_ids)
    if len(report.rules) != 12:
        failures.append("rule-count")
    if any(not item.content_address.startswith("release-policy-rule:") for item in report.rules):
        failures.append("rule-address")
    if any(
        not item.content_address.startswith("release-policy-decision:") for item in report.decisions
    ):
        failures.append("decision-address")
    return tuple(dict.fromkeys(failures))


__all__ = [
    "ReferenceReleasePolicyDecision",
    "ReferenceReleasePolicyReport",
    "ReferenceReleasePolicyRule",
    "default_reference_release_policy_rules",
    "evaluate_reference_release_policy",
    "verify_reference_release_policy",
]
