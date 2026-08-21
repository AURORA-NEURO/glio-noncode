"""Evidence and release policy for C13-C16 frontier atlas surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .frontier_atlas_fixture_eval import FrontierAtlasEvaluationReport
from .frontier_atlas_public_data import (
    FRONTIER_ATLAS_CONTEXT_KEY,
    FRONTIER_ATLAS_EVIDENCE_BOUNDARY,
    FrontierAtlasFixture,
    FrontierAtlasOperation,
)
from .serialization import content_hash, jsonable, require_non_empty


class FrontierAtlasPolicyDisposition(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class FrontierAtlasPolicyRule:
    rule_id: str
    title: str
    requirement: str
    disposition_on_failure: FrontierAtlasPolicyDisposition
    applies_to: tuple[FrontierAtlasOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "title", "requirement", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.applies_to:
            raise ValueError("frontier atlas policy rule requires operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasPolicyCheck:
    rule_id: str
    passed: bool
    disposition: FrontierAtlasPolicyDisposition
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasPolicyReport:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    rules: tuple[FrontierAtlasPolicyRule, ...]
    checks: tuple[FrontierAtlasPolicyCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(
            check.passed and check.disposition is FrontierAtlasPolicyDisposition.PASS
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
    disposition: FrontierAtlasPolicyDisposition,
    applies_to: tuple[FrontierAtlasOperation, ...],
) -> FrontierAtlasPolicyRule:
    body = {
        "rule_id": rule_id,
        "title": title,
        "requirement": requirement,
        "disposition_on_failure": disposition,
        "applies_to": applies_to,
    }
    return FrontierAtlasPolicyRule(**body, content_address=content_hash(body))


def default_frontier_atlas_policy_rules() -> tuple[FrontierAtlasPolicyRule, ...]:
    all_operations = tuple(FrontierAtlasOperation)
    return (
        _rule(
            "scope-public-aggregate",
            "Public aggregate scope",
            "fixture is public aggregate non-patient evidence",
            FrontierAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "context-exact",
            "Exact context",
            "positive records retain exact context",
            FrontierAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "source-closure",
            "Source closure",
            "every record source resolves to a receipt",
            FrontierAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "no-subject-identifiers",
            "No subject identifiers",
            "payloads contain no patient, donor, participant, or sample identifiers",
            FrontierAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "positive-state-floor",
            "Positive state floor",
            "positive records are accepted or published",
            FrontierAtlasPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "controls-visible",
            "Controls visible",
            "controls remain non-accepted/non-published review outcomes",
            FrontierAtlasPolicyDisposition.REVIEW,
            all_operations,
        ),
        _rule(
            "parser-no-fetch",
            "No parser fetch",
            "receipts retain summaries without fixture input text",
            FrontierAtlasPolicyDisposition.DENY,
            all_operations,
        ),
        _rule(
            "absence-not-negative",
            "Absence is not negative",
            "empty snapshot abstention is not a biological-negative claim",
            FrontierAtlasPolicyDisposition.DENY,
            (FrontierAtlasOperation.SNAPSHOT_PUBLISH,),
        ),
        _rule(
            "direction-not-mechanism",
            "Direction is not mechanism",
            "hotspot direction concordance is not a mechanistic conclusion",
            FrontierAtlasPolicyDisposition.DENY,
            (FrontierAtlasOperation.HOTSPOT_ATLAS,),
        ),
        _rule(
            "tier-not-probability",
            "Tier is not probability",
            "evidence tier is a review label, not calibrated confidence",
            FrontierAtlasPolicyDisposition.DENY,
            (FrontierAtlasOperation.EVIDENCE_TIER,),
        ),
        _rule(
            "snapshot-content-address",
            "Snapshot content address",
            "published snapshots retain records and manifest addresses",
            FrontierAtlasPolicyDisposition.DENY,
            (FrontierAtlasOperation.SNAPSHOT_PUBLISH,),
        ),
        _rule(
            "boundary-not-causal",
            "Boundary not causal",
            "insulator boundaries remain descriptive atlas observations",
            FrontierAtlasPolicyDisposition.DENY,
            (FrontierAtlasOperation.BOUNDARY_ATLAS,),
        ),
    )


def evaluate_frontier_atlas_policy(
    fixture: FrontierAtlasFixture,
    evaluation: FrontierAtlasEvaluationReport,
    *,
    rules: tuple[FrontierAtlasPolicyRule, ...] | None = None,
) -> FrontierAtlasPolicyReport:
    selected = rules or default_frontier_atlas_policy_rules()
    source_ids = set(fixture.source_map())
    checks: list[FrontierAtlasPolicyCheck] = []

    def add(rule: FrontierAtlasPolicyRule, passed: bool, detail: str) -> None:
        disposition = FrontierAtlasPolicyDisposition.PASS if passed else rule.disposition_on_failure
        body = {
            "rule_id": rule.rule_id,
            "passed": passed,
            "disposition": disposition,
            "detail": detail,
        }
        checks.append(FrontierAtlasPolicyCheck(**body, content_address=content_hash(body)))

    for rule in selected:
        if rule.rule_id == "scope-public-aggregate":
            add(
                rule,
                fixture.evidence_boundary == FRONTIER_ATLAS_EVIDENCE_BOUNDARY,
                "boundary is public aggregate non-patient",
            )
        elif rule.rule_id == "context-exact":
            add(
                rule,
                fixture.context_key == FRONTIER_ATLAS_CONTEXT_KEY
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
        elif rule.rule_id == "positive-state-floor":
            add(
                rule,
                all(
                    item.adapter_state in {"accepted", "published"}
                    for item in evaluation.receipts
                    if item.role.value == "positive"
                ),
                "positive receipts are accepted or published",
            )
        elif rule.rule_id == "controls-visible":
            add(
                rule,
                all(
                    item.adapter_state not in {"accepted", "published"}
                    for item in evaluation.receipts
                    if item.role.value == "control"
                ),
                "controls remain review states",
            )
        elif rule.rule_id == "parser-no-fetch":
            add(
                rule,
                all(
                    not {"input_text", "payload", "records"} & set(item.summary)
                    for item in evaluation.receipts
                ),
                "receipts are sanitized",
            )
        elif rule.rule_id == "absence-not-negative":
            add(
                rule,
                all(
                    "negative" not in str(item.summary).lower()
                    for item in evaluation.receipts
                    if item.operation is FrontierAtlasOperation.SNAPSHOT_PUBLISH
                ),
                "empty snapshot is abstention only",
            )
        elif rule.rule_id == "direction-not-mechanism":
            add(
                rule,
                all(
                    "mechanism" not in str(item.summary).lower()
                    for item in evaluation.receipts
                    if item.operation is FrontierAtlasOperation.HOTSPOT_ATLAS
                ),
                "hotspot summaries remain descriptive",
            )
        elif rule.rule_id == "tier-not-probability":
            add(
                rule,
                all(
                    "probability" not in str(item.summary).lower()
                    for item in evaluation.receipts
                    if item.operation is FrontierAtlasOperation.EVIDENCE_TIER
                ),
                "tier summaries remain labels",
            )
        elif rule.rule_id == "snapshot-content-address":
            add(
                rule,
                all(
                    item.adapter_state != "published"
                    or (
                        item.summary.get("records_address") and item.summary.get("snapshot_address")
                    )
                    for item in evaluation.receipts
                    if item.operation is FrontierAtlasOperation.SNAPSHOT_PUBLISH
                ),
                "published snapshots expose addresses",
            )
        elif rule.rule_id == "boundary-not-causal":
            add(
                rule,
                all(
                    "causal" not in str(item.summary).lower()
                    for item in evaluation.receipts
                    if item.operation is FrontierAtlasOperation.BOUNDARY_ATLAS
                ),
                "boundary summaries remain descriptive",
            )
        else:
            add(rule, False, "unknown policy rule")
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "rules": selected,
        "checks": checks,
    }
    return FrontierAtlasPolicyReport(
        fixture.fixture_id,
        fixture.context_key,
        fixture.evidence_boundary,
        selected,
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "FrontierAtlasPolicyCheck",
    "FrontierAtlasPolicyDisposition",
    "FrontierAtlasPolicyReport",
    "FrontierAtlasPolicyRule",
    "default_frontier_atlas_policy_rules",
    "evaluate_frontier_atlas_policy",
]
