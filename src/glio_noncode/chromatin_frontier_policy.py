"""Scope and interpretation policy for Domain 07 chromatin evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .chromatin_frontier_fixture_eval import (
    ChromatinFrontierEvaluationReport,
    evaluate_chromatin_frontier_fixture,
)
from .chromatin_frontier_public_data import (
    CHROMATIN_FRONTIER_CONTEXT_KEY,
    CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY,
    ChromatinFrontierFixture,
    ChromatinFrontierOperation,
    default_chromatin_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


class ChromatinFrontierPolicyDisposition(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ChromatinFrontierPolicyRule:
    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: ChromatinFrontierPolicyDisposition
    applies_to: tuple[ChromatinFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "title", "requirement", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.applies_to:
            raise ValueError("chromatin frontier policy rule requires operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierPolicyCheck:
    rule_id: str
    passed: bool
    disposition: ChromatinFrontierPolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierPolicyReport:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[ChromatinFrontierPolicyRule, ...]
    checks: tuple[ChromatinFrontierPolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            item.passed and item.disposition is ChromatinFrontierPolicyDisposition.PASS
            for item in self.checks
        )

    @property
    def failed_rule_ids(self) -> tuple[str, ...]:
        return tuple(item.rule_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_rule_ids": list(self.failed_rule_ids),
        }


def _rule(
    rule_id: str,
    title: str,
    requirement: str,
    disposition: ChromatinFrontierPolicyDisposition,
    applies_to: tuple[ChromatinFrontierOperation, ...],
) -> ChromatinFrontierPolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return ChromatinFrontierPolicyRule(**body, content_address=content_hash(body))


def default_chromatin_frontier_policy_rules() -> tuple[ChromatinFrontierPolicyRule, ...]:
    all_operations = tuple(ChromatinFrontierOperation)
    return (
        _rule(
            "scope-public-aggregate",
            "Public aggregate scope",
            "fixture is public aggregate non-patient evidence",
            ChromatinFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "context-exact",
            "Exact context",
            "positive records retain exact reference and biological context",
            ChromatinFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "source-closure",
            "Source closure",
            "every record source resolves to a receipt",
            ChromatinFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "no-subject-identifiers",
            "No subject identifiers",
            "payloads contain no subject-level identifiers",
            ChromatinFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "positive-state-floor",
            "Positive state floor",
            "positive records are supported",
            ChromatinFrontierPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "controls-visible",
            "Controls visible",
            "controls remain non-supported review outcomes",
            ChromatinFrontierPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "parser-no-fetch",
            "No parser fetch",
            "receipts retain summaries without raw input text",
            ChromatinFrontierPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "segmentation-not-truth",
            "Segmentation is descriptive",
            "chromatin state segments are observations, not enhancer truth",
            ChromatinFrontierPolicyDisposition.DENY,
            (ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,),
        ),
        _rule(
            "allele-not-causal",
            "Allele comparison is descriptive",
            "allele-specific signal deltas are not causal effects",
            ChromatinFrontierPolicyDisposition.DENY,
            (ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN,),
        ),
        _rule(
            "purity-not-clinical",
            "Purity is bounded",
            "epigenomic mixture estimates are not clinical purity calls",
            ChromatinFrontierPolicyDisposition.DENY,
            (ChromatinFrontierOperation.EPIGENOMIC_PURITY,),
        ),
        _rule(
            "correction-terms-visible",
            "Correction terms visible",
            "batch and composition adjustment terms remain inspectable",
            ChromatinFrontierPolicyDisposition.DENY,
            (ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION,),
        ),
        _rule(
            "missing-not-negative",
            "Missing is not negative",
            "missing assay values abstain or remain partial without negative inference",
            ChromatinFrontierPolicyDisposition.DENY,
            all_operations,
        ),
    )


def _contains_subject_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in {"patient", "subject", "donor", "participant", "sample_id"}
            or _contains_subject_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_subject_key(item) for item in value)
    return False


def evaluate_chromatin_frontier_policy(
    fixture: ChromatinFrontierFixture | None = None,
    evaluation: ChromatinFrontierEvaluationReport | None = None,
    *,
    rules: tuple[ChromatinFrontierPolicyRule, ...] | None = None,
) -> ChromatinFrontierPolicyReport:
    selected = fixture or default_chromatin_frontier_fixture()
    report = evaluation or evaluate_chromatin_frontier_fixture(selected)
    selected_rules = rules or default_chromatin_frontier_policy_rules()
    source_ids = set(selected.source_map())
    checks: list[ChromatinFrontierPolicyCheck] = []

    def add(rule: ChromatinFrontierPolicyRule, passed: bool, detail: str) -> None:
        disposition = (
            ChromatinFrontierPolicyDisposition.PASS if passed else rule.disposition_on_failure
        )
        body = {
            "rule_id": rule.rule_id,
            "passed": passed,
            "disposition": disposition,
            "detail": detail,
        }
        checks.append(ChromatinFrontierPolicyCheck(**body, content_address=content_hash(body)))

    for rule in selected_rules:
        if rule.rule_id == "scope-public-aggregate":
            add(
                rule,
                selected.evidence_boundary == CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY,
                "boundary is public aggregate non-patient",
            )
        elif rule.rule_id == "context-exact":
            add(
                rule,
                selected.context_key == CHROMATIN_FRONTIER_CONTEXT_KEY
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
                "every record source resolves",
            )
        elif rule.rule_id == "no-subject-identifiers":
            add(
                rule,
                not any(_contains_subject_key(item.payload) for item in selected.records),
                "fixture payloads are aggregate-scoped",
            )
        elif rule.rule_id == "positive-state-floor":
            add(
                rule,
                report.accepted
                and all(
                    item.adapter_state == "supported"
                    for item in report.receipts
                    if item.role.value == "positive"
                ),
                "positive adapter states are supported",
            )
        elif rule.rule_id == "controls-visible":
            add(
                rule,
                all(
                    item.adapter_state != "supported"
                    for item in report.receipts
                    if item.role.value == "control"
                ),
                "control states remain visible",
            )
        elif rule.rule_id == "parser-no-fetch":
            add(
                rule,
                all("input_text" not in item.summary for item in report.receipts),
                "execution receipts contain summaries only",
            )
        elif rule.rule_id == "segmentation-not-truth":
            add(
                rule,
                all(
                    "truth" not in str(item.summary).lower()
                    for item in report.receipts
                    if item.operation is ChromatinFrontierOperation.CHROMATIN_SEGMENTATION
                ),
                "segment summaries remain descriptive",
            )
        elif rule.rule_id == "allele-not-causal":
            add(
                rule,
                all(
                    "causal" not in str(item.summary).lower()
                    for item in report.receipts
                    if item.operation is ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN
                ),
                "allele summaries retain comparisons only",
            )
        elif rule.rule_id == "purity-not-clinical":
            add(
                rule,
                all(
                    "clinical" not in str(item.summary).lower()
                    for item in report.receipts
                    if item.operation is ChromatinFrontierOperation.EPIGENOMIC_PURITY
                ),
                "purity summaries retain bounded estimates only",
            )
        elif rule.rule_id == "correction-terms-visible":
            add(
                rule,
                all(
                    "corrected_signals" in item.summary
                    for item in report.receipts
                    if item.operation is ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION
                ),
                "correction summaries retain adjusted outputs",
            )
        elif rule.rule_id == "missing-not-negative":
            add(
                rule,
                all(
                    item.adapter_state != "supported"
                    for item in report.receipts
                    if item.role.value == "control"
                ),
                "missing or contradictory controls are not promoted",
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
    return ChromatinFrontierPolicyReport(
        selected.fixture_id,
        selected.context_key,
        selected.evidence_boundary,
        selected_rules,
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "ChromatinFrontierPolicyCheck",
    "ChromatinFrontierPolicyDisposition",
    "ChromatinFrontierPolicyReport",
    "ChromatinFrontierPolicyRule",
    "default_chromatin_frontier_policy_rules",
    "evaluate_chromatin_frontier_policy",
]
