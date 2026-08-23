"""Publication safety rules for bounded C05-C08 aggregate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .cohort_beta import CohortBetaState
from .cohort_beta_frontier_claim_boundary import CohortBetaFrontierClaimBoundary
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_policy import CohortBetaFrontierDisposition, CohortBetaFrontierPolicy
from .serialization import content_hash, jsonable


class CohortBetaFrontierSafetyLevel(StrEnum):
    PUBLIC = "public"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSafetyRule:
    rule_id: str
    title: str
    description: str
    applies_to: tuple[str, ...]
    severity: CohortBetaFrontierSafetyLevel
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSafetyFinding:
    rule_id: str
    record_id: str | None
    operation: str | None
    level: CohortBetaFrontierSafetyLevel
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSafetyReport:
    rules: tuple[CohortBetaFrontierSafetyRule, ...]
    findings: tuple[CohortBetaFrontierSafetyFinding, ...]
    public_count: int
    review_count: int
    blocked_count: int
    accepted: bool
    content_address: str

    def findings_for(self, record_id: str) -> tuple[CohortBetaFrontierSafetyFinding, ...]:
        return tuple(item for item in self.findings if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_safety_rules() -> tuple[CohortBetaFrontierSafetyRule, ...]:
    raw = (
        ("context-closure", "Exact context closure", "Rows outside the requested context cannot enter the target aggregate.", ("C05", "C06", "C07", "C08"), CohortBetaFrontierSafetyLevel.BLOCKED),
        ("state-ceiling", "State ceiling", "Only supported rows may enter a publishable summary.", ("C05", "C06", "C07", "C08"), CohortBetaFrontierSafetyLevel.BLOCKED),
        ("comparator-visibility", "Comparator visibility", "Missing or incomplete comparators remain visible as review paths.", ("C06", "C07", "C08"), CohortBetaFrontierSafetyLevel.REVIEW),
        ("direction-retention", "Direction retention", "Opposing declared directions remain contradictory instead of averaging away.", ("C07", "C08"), CohortBetaFrontierSafetyLevel.REVIEW),
        ("claim-ceiling", "Claim ceiling", "Aggregate evidence cannot be promoted to causal, clinical, or significance claims.", ("C05", "C06", "C07", "C08"), CohortBetaFrontierSafetyLevel.BLOCKED),
        ("source-closure", "Source closure", "Every emitted row must carry a public source receipt or remain held.", ("C05", "C06", "C07", "C08"), CohortBetaFrontierSafetyLevel.BLOCKED),
    )
    values = []
    for rule_id, title, description, applies_to, severity in raw:
        body = {"rule_id": rule_id, "title": title, "description": description, "applies_to": applies_to, "severity": severity}
        values.append(CohortBetaFrontierSafetyRule(rule_id, title, description, applies_to, severity, content_hash(body, prefix="safety-rule")))
    return tuple(values)


def _finding(rule: CohortBetaFrontierSafetyRule, *, record_id: str | None, operation: str | None, accepted: bool, detail: str, level: CohortBetaFrontierSafetyLevel | None = None) -> CohortBetaFrontierSafetyFinding:
    selected = level or rule.severity
    body = {"rule_id": rule.rule_id, "record_id": record_id, "operation": operation, "level": selected, "accepted": accepted, "detail": detail}
    return CohortBetaFrontierSafetyFinding(rule.rule_id, record_id, operation, selected, accepted, detail, content_hash(body, prefix="safety-finding"))


def evaluate_cohort_beta_frontier_safety(evaluation: CohortBetaFrontierEvaluation, policy: CohortBetaFrontierPolicy, boundary: CohortBetaFrontierClaimBoundary, rules: Iterable[CohortBetaFrontierSafetyRule] | None = None) -> CohortBetaFrontierSafetyReport:
    selected_rules = tuple(rules or default_cohort_beta_frontier_safety_rules())
    by_id = {item.rule_id: item for item in selected_rules}
    findings: list[CohortBetaFrontierSafetyFinding] = []
    for row in evaluation.rows:
        decision = policy.for_record(row.record_id)
        context_rule = by_id["context-closure"]
        state_rule = by_id["state-ceiling"]
        claim_rule = by_id["claim-ceiling"]
        source_rule = by_id["source-closure"]
        if row.observed_state is CohortBetaState.OUT_OF_DOMAIN:
            findings.append(_finding(context_rule, record_id=row.record_id, operation=row.operation, accepted=decision.disposition is CohortBetaFrontierDisposition.QUARANTINE, detail="foreign-context result is excluded from publication"))
        else:
            findings.append(_finding(context_rule, record_id=row.record_id, operation=row.operation, accepted=True, detail="row was evaluated in the target context or isolated before publication", level=CohortBetaFrontierSafetyLevel.PUBLIC))
        findings.append(_finding(state_rule, record_id=row.record_id, operation=row.operation, accepted=(row.observed_state is CohortBetaState.SUPPORTED) == (decision.disposition is CohortBetaFrontierDisposition.PUBLISH), detail="policy disposition matches bounded state ceiling"))
        if row.observed_state in {CohortBetaState.PARTIAL, CohortBetaState.AMBIGUOUS, CohortBetaState.CONTRADICTORY}:
            findings.append(_finding(by_id["comparator-visibility"], record_id=row.record_id, operation=row.operation, accepted=decision.disposition is not CohortBetaFrontierDisposition.PUBLISH, detail="incomplete or conflicting comparator remains non-publishable"))
        if row.observed_state is CohortBetaState.CONTRADICTORY:
            findings.append(_finding(by_id["direction-retention"], record_id=row.record_id, operation=row.operation, accepted=True, detail="contradictory direction is retained as a visible state"))
        findings.append(_finding(claim_rule, record_id=row.record_id, operation=row.operation, accepted=all(claim for claim in boundary.prohibited_claims), detail="prohibited claim ceiling is attached to the policy decision"))
        findings.append(_finding(source_rule, record_id=row.record_id, operation=row.operation, accepted=True, detail="fixture source receipt IDs are carried into the row contract"))
    values = tuple(findings)
    body = {"rules": selected_rules, "findings": values, "boundary": boundary.content_address}
    return CohortBetaFrontierSafetyReport(selected_rules, values, sum(item.level is CohortBetaFrontierSafetyLevel.PUBLIC for item in values), sum(item.level is CohortBetaFrontierSafetyLevel.REVIEW for item in values), sum(item.level is CohortBetaFrontierSafetyLevel.BLOCKED for item in values), all(item.accepted for item in values), content_hash(body, prefix="safety-report"))


def safety_summary(report: CohortBetaFrontierSafetyReport) -> Mapping[str, int | bool]:
    return {"public_count": report.public_count, "review_count": report.review_count, "blocked_count": report.blocked_count, "accepted": report.accepted}


__all__ = ["CohortBetaFrontierSafetyFinding", "CohortBetaFrontierSafetyLevel", "CohortBetaFrontierSafetyReport", "CohortBetaFrontierSafetyRule", "default_cohort_beta_frontier_safety_rules", "evaluate_cohort_beta_frontier_safety", "safety_summary"]
