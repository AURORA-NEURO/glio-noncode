"""Policy and integrity checks for Domain 04 C09–C12 evidence artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .reference_governance_fixture_eval import ReferenceGovernanceEvaluationReport
from .reference_governance_public_data import (
    REFERENCE_GOVERNANCE_CONTEXT_KEY,
    REFERENCE_GOVERNANCE_EVIDENCE_BOUNDARY,
    ReferenceGovernanceFixture,
    ReferenceGovernanceOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceGovernancePolicyDisposition(StrEnum):
    """Disposition assigned by a deterministic evidence-boundary rule."""

    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ReferenceGovernancePolicyRule:
    """One named boundary rule with a stable requirement and disposition."""

    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: ReferenceGovernancePolicyDisposition
    applies_to: tuple[ReferenceGovernanceOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.rule_id, "rule_id")
        require_non_empty(self.title, "rule title")
        require_non_empty(self.requirement, "rule requirement")
        if not self.applies_to:
            raise ValueError("policy rule requires operation scope")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernancePolicyCheck:
    """One policy outcome over a fixture or evaluation view."""

    rule_id: str
    passed: bool
    disposition: ReferenceGovernancePolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernancePolicyReport:
    """Policy report covering source scope, context, controls, and sanitization."""

    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[ReferenceGovernancePolicyRule, ...]
    checks: tuple[ReferenceGovernancePolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            check.passed and check.disposition is ReferenceGovernancePolicyDisposition.PASS
            for check in self.checks
        )

    @property
    def failed_rule_ids(self) -> tuple[str, ...]:
        return tuple(check.rule_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_rule_ids": list(self.failed_rule_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _rule(
    rule_id: str,
    title: str,
    requirement: str,
    disposition: ReferenceGovernancePolicyDisposition,
    applies_to: tuple[ReferenceGovernanceOperation, ...],
) -> ReferenceGovernancePolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return ReferenceGovernancePolicyRule(**body, content_address=_address(body))


def default_reference_governance_policy_rules() -> tuple[ReferenceGovernancePolicyRule, ...]:
    """Return the explicit policy set applied to every C09–C12 release."""

    all_operations = tuple(ReferenceGovernanceOperation)
    return (
        _rule(
            "scope-public-aggregate",
            "public aggregate boundary",
            "fixture evidence boundary is public_aggregate_non_patient",
            ReferenceGovernancePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "context-exact",
            "exact context identity",
            "fixture and every record use the declared context key",
            ReferenceGovernancePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "source-closure",
            "source closure",
            "every record source ID resolves to a public source receipt",
            ReferenceGovernancePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "no-subject-identifiers",
            "aggregate-only payload",
            "fixture payloads do not declare subject, patient, or sample identifiers",
            ReferenceGovernancePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "positive-supported",
            "positive support floor",
            "every positive record resolves to supported",
            ReferenceGovernancePolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "controls-visible",
            "control visibility",
            "every control record remains outside supported state",
            ReferenceGovernancePolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "alias-no-description",
            "identifier-only alias boundary",
            "gene identity uses declared identifiers and aliases only",
            ReferenceGovernancePolicyDisposition.REVIEW,
            (ReferenceGovernanceOperation.GENE_ALIAS,),
        ),
        _rule(
            "frequency-descriptive",
            "descriptive frequency boundary",
            "frequency output is not a clinical classification",
            ReferenceGovernancePolicyDisposition.REVIEW,
            (ReferenceGovernanceOperation.POPULATION_FREQUENCY,),
        ),
        _rule(
            "snapshot-no-fetch",
            "manifest-only snapshot boundary",
            "snapshot evaluation does not imply resource-byte retrieval",
            ReferenceGovernancePolicyDisposition.REVIEW,
            (ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,),
        ),
        _rule(
            "permission-deny-missing",
            "deny missing permission",
            "a missing restriction record blocks use",
            ReferenceGovernancePolicyDisposition.DENY,
            (ReferenceGovernanceOperation.LICENSE_RESTRICTION,),
        ),
        _rule(
            "permission-conflict-review",
            "conflict review",
            "conflicting restriction records never select a winner",
            ReferenceGovernancePolicyDisposition.REVIEW,
            (ReferenceGovernanceOperation.LICENSE_RESTRICTION,),
        ),
        _rule(
            "sanitized-receipts",
            "sanitized receipts",
            "execution summaries omit original input collections",
            ReferenceGovernancePolicyDisposition.DENY,
            all_operations,
        ),
    )


def evaluate_reference_governance_policy(
    fixture: ReferenceGovernanceFixture,
    evaluation: ReferenceGovernanceEvaluationReport,
    *,
    rules: tuple[ReferenceGovernancePolicyRule, ...] | None = None,
) -> ReferenceGovernancePolicyReport:
    """Evaluate explicit policy floors over public fixture and receipt views."""

    selected_rules = rules or default_reference_governance_policy_rules()
    source_ids = {source.source_id for source in fixture.sources}
    records_by_operation = {
        operation: tuple(record for record in fixture.records if record.operation is operation)
        for operation in ReferenceGovernanceOperation
    }
    receipts_by_operation = {
        operation: tuple(
            receipt for receipt in evaluation.receipts if receipt.operation is operation
        )
        for operation in ReferenceGovernanceOperation
    }
    outcomes: list[tuple[bool, str]] = []
    for rule in selected_rules:
        applies_records = tuple(
            record for operation in rule.applies_to for record in records_by_operation[operation]
        )
        applies_receipts = tuple(
            receipt for operation in rule.applies_to for receipt in receipts_by_operation[operation]
        )
        if rule.rule_id == "scope-public-aggregate":
            passed = fixture.evidence_boundary == REFERENCE_GOVERNANCE_EVIDENCE_BOUNDARY
            detail = "fixture is within the public aggregate boundary"
        elif rule.rule_id == "context-exact":
            passed = fixture.context_key == REFERENCE_GOVERNANCE_CONTEXT_KEY and all(
                record.context_key == fixture.context_key for record in fixture.records
            )
            detail = "fixture and record context keys agree"
        elif rule.rule_id == "source-closure":
            passed = all(set(record.source_ids) <= source_ids for record in applies_records)
            detail = "record source IDs close over source receipts"
        elif rule.rule_id == "no-subject-identifiers":
            forbidden = {"subject_id", "patient_id", "sample_id"}
            passed = all(not forbidden & set(record.payload) for record in applies_records)
            detail = "payloads contain no subject-level identifier keys"
        elif rule.rule_id == "positive-supported":
            passed = all(
                receipt.adapter_state == "supported"
                for receipt in applies_receipts
                if receipt.role.value == "positive"
            )
            detail = "positive receipts are supported"
        elif rule.rule_id == "controls-visible":
            passed = all(
                receipt.adapter_state != "supported"
                for receipt in applies_receipts
                if receipt.role.value == "control"
            )
            detail = "control receipts remain review states"
        elif rule.rule_id == "alias-no-description":
            passed = all(
                "description" not in record.payload.get("queries", [{}])[0]
                for record in applies_records
            )
            detail = "gene queries use declared identity fields"
        elif rule.rule_id == "frequency-descriptive":
            passed = all(
                "clinical_classification" not in receipt.summary for receipt in applies_receipts
            )
            detail = "frequency summaries retain descriptive fields only"
        elif rule.rule_id == "snapshot-no-fetch":
            passed = all(
                "bytes_fetched" not in receipt.summary and "resource_bytes" not in receipt.summary
                for receipt in applies_receipts
            )
            detail = "snapshot receipts remain manifest-only"
        elif rule.rule_id == "permission-deny-missing":
            missing = next(
                (receipt for receipt in applies_receipts if receipt.record_id == "C12-CTRL-001"),
                None,
            )
            passed = missing is not None and missing.adapter_state == "partial"
            detail = "missing permission control remains blocked"
        elif rule.rule_id == "permission-conflict-review":
            conflict = next(
                (receipt for receipt in applies_receipts if receipt.record_id == "C12-CTRL-003"),
                None,
            )
            passed = conflict is not None and conflict.adapter_state == "contradictory"
            detail = "conflicting permission control remains contradictory"
        elif rule.rule_id == "sanitized-receipts":
            forbidden = {"records", "resources", "restrictions", "queries"}
            passed = all(not forbidden & set(receipt.summary) for receipt in applies_receipts)
            detail = "receipt summaries omit original collections"
        else:
            passed = False
            detail = "unknown policy rule requires review"
        outcomes.append((passed, detail))
    checks: list[ReferenceGovernancePolicyCheck] = []
    for rule, (passed, detail) in zip(selected_rules, outcomes, strict=True):
        disposition = (
            ReferenceGovernancePolicyDisposition.PASS if passed else rule.disposition_on_failure
        )
        body = {
            "rule_id": rule.rule_id,
            "passed": passed,
            "disposition": disposition,
            "detail": detail,
        }
        checks.append(ReferenceGovernancePolicyCheck(**body, content_address=_address(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "rules": selected_rules,
        "checks": checks,
    }
    return ReferenceGovernancePolicyReport(
        fixture.fixture_id,
        fixture.context_key,
        fixture.evidence_boundary,
        selected_rules,
        tuple(checks),
        _address(body),
    )


def verify_reference_governance_policy(report: ReferenceGovernancePolicyReport) -> tuple[str, ...]:
    """Return address and completeness failures for a policy report."""

    failures: list[str] = []
    if report.content_address != _address(
        {
            key: value
            for key, value in report.to_dict().items()
            if key not in {"accepted", "failed_rule_ids", "content_address"}
        }
    ):
        failures.append("policy-address")
    if len(report.rules) != len(report.checks):
        failures.append("rule-check-parity")
    if len({rule.rule_id for rule in report.rules}) != len(report.rules):
        failures.append("rule-identity")
    for rule in report.rules:
        if rule.content_address != _address(
            {key: value for key, value in rule.to_dict().items() if key != "content_address"}
        ):
            failures.append(f"rule-address:{rule.rule_id}")
    for check in report.checks:
        if check.content_address != _address(
            {key: value for key, value in check.to_dict().items() if key != "content_address"}
        ):
            failures.append(f"check-address:{check.rule_id}")
    if not report.accepted:
        failures.append("policy-not-accepted")
    return tuple(failures)


__all__ = [
    "ReferenceGovernancePolicyCheck",
    "ReferenceGovernancePolicyDisposition",
    "ReferenceGovernancePolicyReport",
    "ReferenceGovernancePolicyRule",
    "default_reference_governance_policy_rules",
    "evaluate_reference_governance_policy",
    "verify_reference_governance_policy",
]
