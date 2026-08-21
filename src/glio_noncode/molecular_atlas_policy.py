"""Evidence-boundary policy checks for Domain 05 C05–C08."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .molecular_atlas_fixture_eval import MolecularAtlasEvaluationReport
from .molecular_atlas_public_data import (
    MOLECULAR_ATLAS_CONTEXT_KEY,
    MOLECULAR_ATLAS_EVIDENCE_BOUNDARY,
    MolecularAtlasFixture,
    MolecularAtlasOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


class MolecularAtlasPolicyDisposition(StrEnum):
    """Disposition when a policy requirement is not met."""

    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class MolecularAtlasPolicyRule:
    """One named policy requirement and its operation scope."""

    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: MolecularAtlasPolicyDisposition
    applies_to: tuple[MolecularAtlasOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.rule_id, "rule_id"),
            (self.title, "rule title"),
            (self.requirement, "rule requirement"),
            (self.content_address, "rule content address"),
        ):
            require_non_empty(str(value), name)
        if not self.applies_to:
            raise ValueError("molecular atlas policy rule requires operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasPolicyCheck:
    """One evaluated policy rule."""

    rule_id: str
    passed: bool
    disposition: MolecularAtlasPolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasPolicyReport:
    """Policy report with explicit failure visibility."""

    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[MolecularAtlasPolicyRule, ...]
    checks: tuple[MolecularAtlasPolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            check.passed and check.disposition is MolecularAtlasPolicyDisposition.PASS
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
    disposition: MolecularAtlasPolicyDisposition,
    applies_to: tuple[MolecularAtlasOperation, ...],
) -> MolecularAtlasPolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return MolecularAtlasPolicyRule(**body, content_address=_address(body))


def default_molecular_atlas_policy_rules() -> tuple[MolecularAtlasPolicyRule, ...]:
    """Return the explicit C05–C08 policy set."""

    all_operations = tuple(MolecularAtlasOperation)
    state_operations = tuple(
        operation
        for operation in MolecularAtlasOperation
        if operation is not MolecularAtlasOperation.HISTONE_HARMONIZATION
    )
    histone_operations = (MolecularAtlasOperation.HISTONE_HARMONIZATION,)
    return (
        _rule(
            "scope-public-aggregate",
            "Public aggregate scope",
            "fixture evidence boundary is public aggregate non-patient",
            MolecularAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "context-exact",
            "Exact context",
            "fixture and every record retain an exact declared context",
            MolecularAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "source-closure",
            "Declared source closure",
            "every record source resolves to a public source receipt",
            MolecularAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "no-subject-identifiers",
            "No subject identifiers",
            "payloads do not contain subject, patient, donor, or sample identifiers",
            MolecularAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "state-separation",
            "State separation",
            "IDH-mutant, IDH-wildtype, and H3K27-altered rows stay within their operation state",
            MolecularAtlasPolicyDisposition.DENY,
            state_operations,
        ),
        _rule(
            "positive-supported",
            "Positive support",
            "positive state or histone receipts are supported",
            MolecularAtlasPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "controls-visible",
            "Visible controls",
            "control receipts remain non-supported review states",
            MolecularAtlasPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "parser-no-fetch",
            "No fetch in parser",
            "receipt summaries retain hashes and counts without input text",
            MolecularAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "absence-not-negative",
            "Absence is not negative",
            "absence and abstention do not carry a biological-negative field",
            MolecularAtlasPolicyDisposition.DENY,
            state_operations,
        ),
        _rule(
            "ambiguity-not-selection",
            "Ambiguity is not selection",
            "ambiguous state or signal outcomes do not select a preferred record",
            MolecularAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "histone-replicate-floor",
            "Histone replicate floor",
            "histone support requires at least two compatible replicates",
            MolecularAtlasPolicyDisposition.REVIEW,
            histone_operations,
        ),
        _rule(
            "no-activity-inference",
            "No activity inference",
            "receipts contain descriptive signal summaries rather than activity or causal claims",
            MolecularAtlasPolicyDisposition.DENY,
            all_operations,
        ),
    )


def evaluate_molecular_atlas_policy(
    fixture: MolecularAtlasFixture,
    evaluation: MolecularAtlasEvaluationReport,
    *,
    rules: tuple[MolecularAtlasPolicyRule, ...] | None = None,
) -> MolecularAtlasPolicyReport:
    """Evaluate every explicit C05–C08 evidence-boundary rule."""

    selected_rules = rules or default_molecular_atlas_policy_rules()
    source_ids = {source.source_id for source in fixture.sources}
    records_by_operation = {
        operation: tuple(record for record in fixture.records if record.operation is operation)
        for operation in MolecularAtlasOperation
    }
    receipts_by_operation = {
        operation: tuple(
            receipt for receipt in evaluation.receipts if receipt.operation is operation
        )
        for operation in MolecularAtlasOperation
    }
    outcomes: list[tuple[bool, str]] = []
    state_for_operation = {
        MolecularAtlasOperation.IDH_MUTANT_PROFILE: "IDH-mutant",
        MolecularAtlasOperation.IDH_WILDTYPE_PROFILE: "IDH-wildtype",
        MolecularAtlasOperation.H3K27_ALTERED_PROFILE: "H3K27-altered",
    }
    for rule in selected_rules:
        records = tuple(
            record for operation in rule.applies_to for record in records_by_operation[operation]
        )
        receipts = tuple(
            receipt for operation in rule.applies_to for receipt in receipts_by_operation[operation]
        )
        if rule.rule_id == "scope-public-aggregate":
            passed, detail = (
                fixture.evidence_boundary == MOLECULAR_ATLAS_EVIDENCE_BOUNDARY,
                "fixture is within public aggregate scope",
            )
        elif rule.rule_id == "context-exact":
            passed = fixture.context_key == MOLECULAR_ATLAS_CONTEXT_KEY and all(
                record.context_key for record in fixture.records
            )
            detail = "fixture and records declare context keys"
        elif rule.rule_id == "source-closure":
            passed, detail = (
                all(set(record.source_ids) <= source_ids for record in records),
                "all record sources resolve",
            )
        elif rule.rule_id == "no-subject-identifiers":
            forbidden = {"subject_id", "patient_id", "sample_id", "donor_id"}
            passed = all(not forbidden & set(record.payload) for record in records)
            detail = "payloads contain no subject-level identifiers"
        elif rule.rule_id == "state-separation":
            passed = all(
                record.payload.get("molecular_state") == state_for_operation[record.operation]
                for record in records
            )
            detail = "state rows remain tied to their operation family"
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
            detail = "receipts contain no input text"
        elif rule.rule_id == "absence-not-negative":
            passed = all(not receipt.summary.get("biological_negative") for receipt in receipts)
            detail = "abstention carries no biological-negative field"
        elif rule.rule_id == "ambiguity-not-selection":
            passed = all(
                not {"selected_id", "selected_record"} & set(receipt.summary)
                for receipt in receipts
                if receipt.adapter_state == "ambiguous"
            )
            detail = "ambiguous receipts select no row"
        elif rule.rule_id == "histone-replicate-floor":
            passed = all(
                receipt.adapter_state != "supported"
                or receipt.summary.get("replicate_counts") == (2,)
                for receipt in receipts
            )
            detail = "supported histone intervals retain two-replicate evidence"
        elif rule.rule_id == "no-activity-inference":
            passed = all(
                not {"activity_call", "causal_claim", "clinical_call"} & set(receipt.summary)
                for receipt in receipts
            )
            detail = "summaries retain descriptive dimensions only"
        else:
            passed, detail = False, "unknown policy rule requires review"
        outcomes.append((passed, detail))
    checks: list[MolecularAtlasPolicyCheck] = []
    for rule, (passed, detail) in zip(selected_rules, outcomes, strict=True):
        disposition = (
            MolecularAtlasPolicyDisposition.PASS if passed else rule.disposition_on_failure
        )
        body = {
            "rule_id": rule.rule_id,
            "passed": passed,
            "disposition": disposition,
            "detail": detail,
        }
        checks.append(MolecularAtlasPolicyCheck(**body, content_address=_address(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "rules": selected_rules,
        "checks": checks,
    }
    return MolecularAtlasPolicyReport(
        fixture.fixture_id,
        fixture.context_key,
        fixture.evidence_boundary,
        selected_rules,
        tuple(checks),
        _address(body),
    )


def verify_molecular_atlas_policy(report: MolecularAtlasPolicyReport) -> tuple[str, ...]:
    """Return policy address, parity, and completeness failures."""

    failures: list[str] = []
    expected = {
        key: value
        for key, value in report.to_dict().items()
        if key not in {"accepted", "failed_rule_ids", "content_address"}
    }
    if report.content_address != _address(expected):
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
    "MolecularAtlasPolicyCheck",
    "MolecularAtlasPolicyDisposition",
    "MolecularAtlasPolicyReport",
    "MolecularAtlasPolicyRule",
    "default_molecular_atlas_policy_rules",
    "evaluate_molecular_atlas_policy",
    "verify_molecular_atlas_policy",
]
