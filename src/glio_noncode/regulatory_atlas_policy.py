"""Evidence-boundary policy checks for Domain 05 C01–C04."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .regulatory_atlas_fixture_eval import RegulatoryAtlasEvaluationReport
from .regulatory_atlas_public_data import (
    REGULATORY_ATLAS_CONTEXT_KEY,
    REGULATORY_ATLAS_EVIDENCE_BOUNDARY,
    RegulatoryAtlasFixture,
    RegulatoryAtlasOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


class RegulatoryAtlasPolicyDisposition(StrEnum):
    """Disposition when a policy requirement is not met."""

    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasPolicyRule:
    """One named rule and its operation scope."""

    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: RegulatoryAtlasPolicyDisposition
    applies_to: tuple[RegulatoryAtlasOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.rule_id, "rule_id"),
            (self.title, "rule title"),
            (self.requirement, "rule requirement"),
        ):
            require_non_empty(value, name)
        if not self.applies_to:
            raise ValueError("regulatory policy rule requires operation scope")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasPolicyCheck:
    """One policy outcome."""

    rule_id: str
    passed: bool
    disposition: RegulatoryAtlasPolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasPolicyReport:
    """Policy report over fixture scope and sanitized execution receipts."""

    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[RegulatoryAtlasPolicyRule, ...]
    checks: tuple[RegulatoryAtlasPolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            check.passed and check.disposition is RegulatoryAtlasPolicyDisposition.PASS
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
    disposition: RegulatoryAtlasPolicyDisposition,
    applies_to: tuple[RegulatoryAtlasOperation, ...],
) -> RegulatoryAtlasPolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return RegulatoryAtlasPolicyRule(**body, content_address=_address(body))


def default_regulatory_atlas_policy_rules() -> tuple[RegulatoryAtlasPolicyRule, ...]:
    """Return the policy set applied to every C01–C04 release."""

    all_operations = tuple(RegulatoryAtlasOperation)
    profile_operations = tuple(
        operation
        for operation in all_operations
        if operation is not RegulatoryAtlasOperation.CCRE_PARSE
    )
    return (
        _rule(
            "scope-public-aggregate",
            "public aggregate scope",
            "fixture is public_aggregate_non_patient",
            RegulatoryAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "context-exact",
            "exact atlas context",
            "fixture and records use the declared context key",
            RegulatoryAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "source-closure",
            "source closure",
            "record source IDs resolve to public receipts",
            RegulatoryAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "no-subject-identifiers",
            "aggregate-only payload",
            "payloads contain no subject, patient, or sample fields",
            RegulatoryAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "positive-supported",
            "positive support floor",
            "positive records produce supported receipts",
            RegulatoryAtlasPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "controls-visible",
            "control visibility",
            "controls remain outside supported state",
            RegulatoryAtlasPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "parser-no-fetch",
            "parser boundary",
            "parse receipts retain hashes without downloading cCRE bytes",
            RegulatoryAtlasPolicyDisposition.REVIEW,
            (RegulatoryAtlasOperation.CCRE_PARSE,),
        ),
        _rule(
            "profile-context-gate",
            "profile context gate",
            "profile queries use explicit ReferenceContext values",
            RegulatoryAtlasPolicyDisposition.REVIEW,
            profile_operations,
        ),
        _rule(
            "absence-not-negative",
            "absence semantics",
            "absent overlap is not a biological negative",
            RegulatoryAtlasPolicyDisposition.REVIEW,
            profile_operations,
        ),
        _rule(
            "ambiguity-not-selection",
            "ambiguity semantics",
            "multiple overlaps remain ambiguous",
            RegulatoryAtlasPolicyDisposition.REVIEW,
            profile_operations,
        ),
        _rule(
            "no-activity-inference",
            "activity boundary",
            "overlap is not promoted to activity or causality",
            RegulatoryAtlasPolicyDisposition.DENY,
            profile_operations,
        ),
        _rule(
            "sanitized-receipts",
            "sanitized output",
            "receipts omit original input text and collections",
            RegulatoryAtlasPolicyDisposition.DENY,
            all_operations,
        ),
    )


def evaluate_regulatory_atlas_policy(
    fixture: RegulatoryAtlasFixture,
    evaluation: RegulatoryAtlasEvaluationReport,
    *,
    rules: tuple[RegulatoryAtlasPolicyRule, ...] | None = None,
) -> RegulatoryAtlasPolicyReport:
    """Evaluate all explicit C01–C04 evidence-boundary policies."""

    selected_rules = rules or default_regulatory_atlas_policy_rules()
    source_ids = {source.source_id for source in fixture.sources}
    records_by_operation = {
        operation: tuple(record for record in fixture.records if record.operation is operation)
        for operation in RegulatoryAtlasOperation
    }
    receipts_by_operation = {
        operation: tuple(
            receipt for receipt in evaluation.receipts if receipt.operation is operation
        )
        for operation in RegulatoryAtlasOperation
    }
    outcomes: list[tuple[bool, str]] = []
    for rule in selected_rules:
        records = tuple(
            record for operation in rule.applies_to for record in records_by_operation[operation]
        )
        receipts = tuple(
            receipt for operation in rule.applies_to for receipt in receipts_by_operation[operation]
        )
        if rule.rule_id == "scope-public-aggregate":
            passed, detail = (
                fixture.evidence_boundary == REGULATORY_ATLAS_EVIDENCE_BOUNDARY,
                "fixture is within public aggregate scope",
            )
        elif rule.rule_id == "context-exact":
            passed = fixture.context_key == REGULATORY_ATLAS_CONTEXT_KEY and all(
                record.context_key == fixture.context_key for record in fixture.records
            )
            detail = "fixture and record contexts agree"
        elif rule.rule_id == "source-closure":
            passed, detail = (
                all(set(record.source_ids) <= source_ids for record in records),
                "all record sources resolve",
            )
        elif rule.rule_id == "no-subject-identifiers":
            passed = all(
                not {"subject_id", "patient_id", "sample_id"} & set(record.payload)
                for record in records
            )
            detail = "payloads contain no subject-level identifiers"
        elif rule.rule_id == "positive-supported":
            passed = all(
                receipt.adapter_state == "supported"
                for receipt in receipts
                if receipt.role.value == "positive"
            )
            detail = "positive receipts are supported"
        elif rule.rule_id == "controls-visible":
            passed = all(
                receipt.adapter_state != "supported"
                for receipt in receipts
                if receipt.role.value == "control"
            )
            detail = "control receipts remain review states"
        elif rule.rule_id == "parser-no-fetch":
            passed = all("input_text" not in receipt.summary for receipt in receipts)
            detail = "parse receipts retain no input text"
        elif rule.rule_id == "profile-context-gate":
            passed = all("context_key" in receipt.summary for receipt in receipts)
            detail = "profile receipts retain exact query context"
        elif rule.rule_id == "absence-not-negative":
            passed = all(
                not (
                    receipt.adapter_state == "absent" and receipt.summary.get("biological_negative")
                )
                for receipt in receipts
            )
            detail = "absence receipts have no biological-negative field"
        elif rule.rule_id == "ambiguity-not-selection":
            passed = all(
                not (receipt.adapter_state == "ambiguous" and receipt.summary.get("selected_id"))
                for receipt in receipts
            )
            detail = "ambiguous receipts select no record"
        elif rule.rule_id == "no-activity-inference":
            passed = all(
                not {"activity_call", "causal_claim"} & set(receipt.summary) for receipt in receipts
            )
            detail = "profile summaries retain overlap evidence only"
        elif rule.rule_id == "sanitized-receipts":
            passed = all(
                not {"input_text", "records", "payload"} & set(receipt.summary)
                for receipt in receipts
            )
            detail = "receipts omit source collections and text"
        else:
            passed, detail = False, "unknown policy rule requires review"
        outcomes.append((passed, detail))
    checks: list[RegulatoryAtlasPolicyCheck] = []
    for rule, (passed, detail) in zip(selected_rules, outcomes, strict=True):
        disposition = (
            RegulatoryAtlasPolicyDisposition.PASS if passed else rule.disposition_on_failure
        )
        body = {
            "rule_id": rule.rule_id,
            "passed": passed,
            "disposition": disposition,
            "detail": detail,
        }
        checks.append(RegulatoryAtlasPolicyCheck(**body, content_address=_address(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "rules": selected_rules,
        "checks": checks,
    }
    return RegulatoryAtlasPolicyReport(
        fixture.fixture_id,
        fixture.context_key,
        fixture.evidence_boundary,
        selected_rules,
        tuple(checks),
        _address(body),
    )


def verify_regulatory_atlas_policy(report: RegulatoryAtlasPolicyReport) -> tuple[str, ...]:
    """Return address and completeness failures."""

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
    "RegulatoryAtlasPolicyCheck",
    "RegulatoryAtlasPolicyDisposition",
    "RegulatoryAtlasPolicyReport",
    "RegulatoryAtlasPolicyRule",
    "default_regulatory_atlas_policy_rules",
    "evaluate_regulatory_atlas_policy",
    "verify_regulatory_atlas_policy",
]
