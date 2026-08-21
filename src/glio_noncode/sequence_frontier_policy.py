"""State, source, and interpretation policy for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .sequence_frontier_fixture_eval import (
    SequenceFrontierEvaluationReport,
    evaluate_sequence_frontier_fixture,
)
from .sequence_frontier_public_data import (
    SEQUENCE_FRONTIER_CONTEXT_KEY,
    SEQUENCE_FRONTIER_EVIDENCE_BOUNDARY,
    SequenceFrontierFixture,
    SequenceFrontierOperation,
    default_sequence_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


class SequenceFrontierPolicyDisposition(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class SequenceFrontierPolicyRule:
    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: SequenceFrontierPolicyDisposition
    applies_to: tuple[SequenceFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "title", "requirement", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.applies_to:
            raise ValueError("sequence frontier policy rule requires operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierPolicyCheck:
    rule_id: str
    passed: bool
    disposition: SequenceFrontierPolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierPolicyReport:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[SequenceFrontierPolicyRule, ...]
    checks: tuple[SequenceFrontierPolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            item.passed and item.disposition is SequenceFrontierPolicyDisposition.PASS
            for item in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _rule(
    rule_id: str,
    title: str,
    requirement: str,
    disposition: SequenceFrontierPolicyDisposition,
    applies_to: tuple[SequenceFrontierOperation, ...],
) -> SequenceFrontierPolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return SequenceFrontierPolicyRule(**body, content_address=content_hash(body))


def default_sequence_frontier_policy_rules() -> tuple[SequenceFrontierPolicyRule, ...]:
    all_operations = tuple(SequenceFrontierOperation)
    return (
        _rule(
            "scope-public-aggregate",
            "Public aggregate scope",
            "fixture is public aggregate non-patient evidence",
            SequenceFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "context-exact",
            "Exact context",
            "positive records retain exact context",
            SequenceFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "source-closure",
            "Source closure",
            "every record source resolves to a receipt",
            SequenceFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "no-subject-identifiers",
            "No subject identifiers",
            "payloads contain no subject, donor, participant, or sample identifiers",
            SequenceFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "positive-state-floor",
            "Positive state floor",
            "positive records are accepted or published",
            SequenceFrontierPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "controls-visible",
            "Controls visible",
            "controls remain non-success review outcomes",
            SequenceFrontierPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "parser-no-fetch",
            "No parser fetch",
            "receipts retain summaries without raw input text",
            SequenceFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "absence-not-negative",
            "Absence is not negative",
            "empty evidence abstention is not a biological-negative claim",
            SequenceFrontierPolicyDisposition.DENY,
            (SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,),
        ),
        _rule(
            "grammar-not-activity",
            "Grammar is not activity",
            "motif grammar compatibility is descriptive",
            SequenceFrontierPolicyDisposition.DENY,
            (SequenceFrontierOperation.ENHANCER_GRAMMAR,),
        ),
        _rule(
            "saturation-not-effect",
            "Saturation is not effect proof",
            "alternate score deltas retain uncertainty",
            SequenceFrontierPolicyDisposition.DENY,
            (SequenceFrontierOperation.ALLELE_SATURATION,),
        ),
        _rule(
            "ensemble-not-probability",
            "Ensemble is not probability",
            "spread and interval are descriptive model comparisons",
            SequenceFrontierPolicyDisposition.DENY,
            (SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT,),
        ),
        _rule(
            "publish-addresses",
            "Publication addresses",
            "published sequence evidence retains records and bundle addresses",
            SequenceFrontierPolicyDisposition.DENY,
            (SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,),
        ),
    )


def evaluate_sequence_frontier_policy(
    fixture: SequenceFrontierFixture | None = None,
    evaluation: SequenceFrontierEvaluationReport | None = None,
    *,
    rules: tuple[SequenceFrontierPolicyRule, ...] | None = None,
) -> SequenceFrontierPolicyReport:
    selected = fixture or default_sequence_frontier_fixture()
    report = evaluation or evaluate_sequence_frontier_fixture(selected)
    selected_rules = rules or default_sequence_frontier_policy_rules()
    source_ids = set(selected.source_map())
    checks: list[SequenceFrontierPolicyCheck] = []

    def add(rule: SequenceFrontierPolicyRule, passed: bool, detail: str) -> None:
        disposition = (
            SequenceFrontierPolicyDisposition.PASS if passed else rule.disposition_on_failure
        )
        body = {
            "rule_id": rule.rule_id,
            "passed": passed,
            "disposition": disposition,
            "detail": detail,
        }
        checks.append(SequenceFrontierPolicyCheck(**body, content_address=content_hash(body)))

    for rule in selected_rules:
        if rule.rule_id == "scope-public-aggregate":
            add(
                rule,
                selected.evidence_boundary == SEQUENCE_FRONTIER_EVIDENCE_BOUNDARY,
                "boundary is public aggregate non-patient",
            )
        elif rule.rule_id == "context-exact":
            add(
                rule,
                selected.context_key == SEQUENCE_FRONTIER_CONTEXT_KEY
                and all(
                    item.context_key == selected.context_key for item in selected.positive_records
                ),
                "positive context is exact",
            )
        elif rule.rule_id == "source-closure":
            add(
                rule,
                all(
                    source_id in source_ids
                    for item in selected.records
                    for source_id in item.source_ids
                ),
                "source closure resolves",
            )
        elif rule.rule_id == "no-subject-identifiers":
            add(
                rule,
                all(
                    not {"patient", "subject", "donor", "participant", "sample_id"}
                    & {key.lower() for key in item.payload}
                    for item in selected.records
                ),
                "payload keys have no subject identifiers",
            )
        elif rule.rule_id == "positive-state-floor":
            add(
                rule,
                all(
                    item.adapter_state in {"accepted", "published"}
                    for item in report.receipts
                    if item.role.value == "positive"
                ),
                "positive receipts are accepted or published",
            )
        elif rule.rule_id == "controls-visible":
            add(
                rule,
                all(
                    item.adapter_state not in {"accepted", "published"}
                    for item in report.receipts
                    if item.role.value == "control"
                ),
                "controls remain visible",
            )
        elif rule.rule_id == "parser-no-fetch":
            add(
                rule,
                all(
                    not {"input_text", "payload", "records"} & set(item.summary)
                    for item in report.receipts
                ),
                "receipts are sanitized",
            )
        elif rule.rule_id == "absence-not-negative":
            add(
                rule,
                all(
                    "negative" not in str(item.summary).lower()
                    for item in report.receipts
                    if item.operation is SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH
                ),
                "empty evidence is abstention only",
            )
        elif rule.rule_id == "grammar-not-activity":
            add(
                rule,
                all(
                    "activity" not in str(item.summary).lower()
                    for item in report.receipts
                    if item.operation is SequenceFrontierOperation.ENHANCER_GRAMMAR
                ),
                "grammar remains descriptive",
            )
        elif rule.rule_id == "saturation-not-effect":
            add(
                rule,
                all(
                    "effect proof" not in str(item.summary).lower()
                    for item in report.receipts
                    if item.operation is SequenceFrontierOperation.ALLELE_SATURATION
                ),
                "saturation retains uncertainty",
            )
        elif rule.rule_id == "ensemble-not-probability":
            add(
                rule,
                all(
                    "probability" not in str(item.summary).lower()
                    for item in report.receipts
                    if item.operation is SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT
                ),
                "ensemble remains descriptive",
            )
        elif rule.rule_id == "publish-addresses":
            add(
                rule,
                all(
                    item.adapter_state != "published"
                    or (item.summary.get("records_address") and item.summary.get("bundle_address"))
                    for item in report.receipts
                    if item.operation is SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH
                ),
                "published outputs expose addresses",
            )
        else:
            add(rule, False, "unknown policy rule")
    body = {
        "fixture_id": selected.fixture_id,
        "context_key": selected.context_key,
        "evidence_boundary": selected.evidence_boundary,
        "rules": selected_rules,
        "checks": checks,
    }
    return SequenceFrontierPolicyReport(
        selected.fixture_id,
        selected.context_key,
        selected.evidence_boundary,
        selected_rules,
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "SequenceFrontierPolicyCheck",
    "SequenceFrontierPolicyDisposition",
    "SequenceFrontierPolicyReport",
    "SequenceFrontierPolicyRule",
    "default_sequence_frontier_policy_rules",
    "evaluate_sequence_frontier_policy",
]
