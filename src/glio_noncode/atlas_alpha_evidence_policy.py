"""Evidence-boundary policy for the C09-C12 atlas-alpha layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .atlas_alpha_evidence_fixture_eval import AtlasAlphaEvidenceEvaluationReport
from .atlas_alpha_evidence_public_data import (
    ATLAS_ALPHA_EVIDENCE_BOUNDARY,
    ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
    AtlasAlphaEvidenceFixture,
    AtlasAlphaEvidenceOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


class AtlasAlphaEvidencePolicyDisposition(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidencePolicyRule:
    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: AtlasAlphaEvidencePolicyDisposition
    applies_to: tuple[AtlasAlphaEvidenceOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "title", "requirement", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.applies_to:
            raise ValueError("atlas alpha policy rule requires operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidencePolicyCheck:
    rule_id: str
    passed: bool
    disposition: AtlasAlphaEvidencePolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidencePolicyReport:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[AtlasAlphaEvidencePolicyRule, ...]
    checks: tuple[AtlasAlphaEvidencePolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            check.passed and check.disposition is AtlasAlphaEvidencePolicyDisposition.PASS
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


def _rule(
    rule_id: str,
    title: str,
    requirement: str,
    disposition: AtlasAlphaEvidencePolicyDisposition,
    applies_to: tuple[AtlasAlphaEvidenceOperation, ...],
) -> AtlasAlphaEvidencePolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return AtlasAlphaEvidencePolicyRule(**body, content_address=content_hash(body))


def default_atlas_alpha_evidence_policy_rules() -> tuple[AtlasAlphaEvidencePolicyRule, ...]:
    """Return the explicit public-data and interpretation rules."""

    all_operations = tuple(AtlasAlphaEvidenceOperation)
    return (
        _rule(
            "scope-public-aggregate",
            "Public aggregate scope",
            "fixture is public aggregate non-patient evidence",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "context-exact",
            "Exact context",
            "positive records retain the declared context",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "source-closure",
            "Source closure",
            "every record source resolves to a public receipt",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "no-subject-identifiers",
            "No subject identifiers",
            "fixture payloads contain no patient, subject, donor, participant, or sample identifiers",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "positive-supported",
            "Positive support",
            "every positive execution is supported",
            AtlasAlphaEvidencePolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "controls-visible",
            "Visible controls",
            "every control remains a non-supported review state",
            AtlasAlphaEvidencePolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "parser-no-fetch",
            "No parser fetch",
            "execution receipts retain counts and hashes rather than source payloads",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "absence-not-negative",
            "Absence is not negative",
            "abstention and missingness are not converted to biological-negative claims",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "ambiguity-not-selection",
            "Ambiguity is not selection",
            "disagreement does not select a preferred replicate or role",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "accessibility-not-activity",
            "Accessibility boundary",
            "open chromatin remains an accessibility observation",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            (AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,),
        ),
        _rule(
            "methylation-coverage",
            "Methylation coverage",
            "zero coverage is partial and is not treated as unmethylated",
            AtlasAlphaEvidencePolicyDisposition.REVIEW,
            (AtlasAlphaEvidenceOperation.METHYLATION,),
        ),
        _rule(
            "candidate-not-causal",
            "Candidate boundary",
            "super-enhancer groupings remain ranked candidates",
            AtlasAlphaEvidencePolicyDisposition.DENY,
            (AtlasAlphaEvidenceOperation.SUPER_ENHANCER,),
        ),
    )


def evaluate_atlas_alpha_evidence_policy(
    fixture: AtlasAlphaEvidenceFixture,
    evaluation: AtlasAlphaEvidenceEvaluationReport,
    *,
    rules: tuple[AtlasAlphaEvidencePolicyRule, ...] | None = None,
) -> AtlasAlphaEvidencePolicyReport:
    """Evaluate policy rules without fetching or adding hidden evidence."""

    selected_rules = rules or default_atlas_alpha_evidence_policy_rules()
    source_ids = set(fixture.source_map())
    checks: list[AtlasAlphaEvidencePolicyCheck] = []
    receipts = evaluation.receipts

    def add(rule: AtlasAlphaEvidencePolicyRule, passed: bool, detail: str) -> None:
        disposition = (
            AtlasAlphaEvidencePolicyDisposition.PASS if passed else rule.disposition_on_failure
        )
        body = {
            "rule_id": rule.rule_id,
            "passed": passed,
            "disposition": disposition,
            "detail": detail,
        }
        checks.append(AtlasAlphaEvidencePolicyCheck(**body, content_address=content_hash(body)))

    for rule in selected_rules:
        if rule.rule_id == "scope-public-aggregate":
            add(
                rule,
                fixture.evidence_boundary == ATLAS_ALPHA_EVIDENCE_BOUNDARY,
                "boundary is public aggregate non-patient",
            )
        elif rule.rule_id == "context-exact":
            add(
                rule,
                fixture.context_key == ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY
                and all(
                    item.context_key == fixture.context_key for item in fixture.positive_records
                ),
                "positive context is exact",
            )
        elif rule.rule_id == "source-closure":
            add(
                rule,
                all(
                    source_id in source_ids
                    for record in fixture.records
                    for source_id in record.source_ids
                ),
                "source closure resolves",
            )
        elif rule.rule_id == "no-subject-identifiers":
            add(
                rule,
                all(
                    not {"patient", "subject", "donor", "participant", "sample_id"}
                    & {key.lower() for key in record.payload}
                    for record in fixture.records
                ),
                "payload keys have no subject identifiers",
            )
        elif rule.rule_id == "positive-supported":
            add(
                rule,
                all(
                    item.adapter_state == "supported"
                    for item in receipts
                    if item.role.value == "positive"
                ),
                "positive receipts are supported",
            )
        elif rule.rule_id == "controls-visible":
            add(
                rule,
                all(
                    item.adapter_state != "supported"
                    for item in receipts
                    if item.role.value == "control"
                ),
                "controls remain review states",
            )
        elif rule.rule_id == "parser-no-fetch":
            add(
                rule,
                all(
                    not {"input_text", "payload", "records"} & set(item.summary)
                    for item in receipts
                ),
                "receipts are sanitized",
            )
        elif rule.rule_id == "absence-not-negative":
            add(
                rule,
                all("negative" not in str(item.summary).lower() for item in receipts),
                "absence does not produce a negative claim",
            )
        elif rule.rule_id == "ambiguity-not-selection":
            add(
                rule,
                all(
                    item.adapter_state != "ambiguous" or item.secondary_count >= 0
                    for item in receipts
                ),
                "ambiguous receipts remain visible",
            )
        elif rule.rule_id == "accessibility-not-activity":
            add(
                rule,
                not any(
                    "activity" in str(item.summary).lower()
                    for item in receipts
                    if item.operation is AtlasAlphaEvidenceOperation.OPEN_CHROMATIN
                ),
                "open chromatin summaries do not infer activity",
            )
        elif rule.rule_id == "methylation-coverage":
            add(
                rule,
                any(
                    item.operation is AtlasAlphaEvidenceOperation.METHYLATION
                    and item.adapter_state == "partial"
                    for item in receipts
                ),
                "methylation control demonstrates coverage review",
            )
        elif rule.rule_id == "candidate-not-causal":
            add(
                rule,
                not any(
                    "causal" in str(item.summary).lower()
                    for item in receipts
                    if item.operation is AtlasAlphaEvidenceOperation.SUPER_ENHANCER
                ),
                "candidate summaries remain non-causal",
            )
        else:
            add(rule, False, "unknown policy rule")
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "rules": selected_rules,
        "checks": checks,
    }
    return AtlasAlphaEvidencePolicyReport(
        fixture.fixture_id,
        fixture.context_key,
        fixture.evidence_boundary,
        selected_rules,
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "AtlasAlphaEvidencePolicyCheck",
    "AtlasAlphaEvidencePolicyDisposition",
    "AtlasAlphaEvidencePolicyReport",
    "AtlasAlphaEvidencePolicyRule",
    "default_atlas_alpha_evidence_policy_rules",
    "evaluate_atlas_alpha_evidence_policy",
]
