"""Governance rules for public beta review, scope, and release decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierGovernanceRule:
    rule_id: str
    title: str
    applies_to: tuple[str, ...]
    requirement: str
    evidence_field: str
    failure_action: str
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierGovernanceDecision:
    rule_id: str
    operation: str
    passed: bool
    observed: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierGovernanceReport:
    rules: tuple[TopologyBetaFrontierGovernanceRule, ...]
    decisions: tuple[TopologyBetaFrontierGovernanceDecision, ...]
    blocking_failures: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def decisions_for(self, operation: str) -> tuple[TopologyBetaFrontierGovernanceDecision, ...]:
        return tuple(item for item in self.decisions if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rules": [item.to_dict() for item in self.rules], "decisions": [item.to_dict() for item in self.decisions], "blocking_failures": self.blocking_failures, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_beta_frontier_governance_rules() -> tuple[TopologyBetaFrontierGovernanceRule, ...]:
    return (
        TopologyBetaFrontierGovernanceRule("scope", "Public aggregate scope", ("loop_stripe", "promoter_capture", "enhancer_promoter_contact", "activity_by_contact"), "Every payload declares public aggregate scope.", "public_aggregate", "block release", True),
        TopologyBetaFrontierGovernanceRule("context", "Exact context gate", ("loop_stripe", "promoter_capture", "enhancer_promoter_contact", "activity_by_contact"), "Foreign context remains out of domain.", "context_key", "block transport", True),
        TopologyBetaFrontierGovernanceRule("lineage", "Source and evidence closure", ("loop_stripe", "promoter_capture", "enhancer_promoter_contact", "activity_by_contact"), "Every replay retains source and result receipts.", "source_ids", "route to review", True),
        TopologyBetaFrontierGovernanceRule("missingness", "Explicit missingness", ("enhancer_promoter_contact", "activity_by_contact"), "Absent and abstained paths remain explicit.", "issue_codes", "retain missingness", False),
        TopologyBetaFrontierGovernanceRule("score-bound", "Bounded score output", ("enhancer_promoter_contact", "activity_by_contact"), "Descriptive scores remain bounded under declared scales.", "measurements", "route to review", True),
        TopologyBetaFrontierGovernanceRule("review", "Control visibility", ("loop_stripe", "promoter_capture", "enhancer_promoter_contact", "activity_by_contact"), "Every control remains visible for review.", "role", "block release", True),
    )


def build_topology_beta_frontier_governance(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierGovernanceReport:
    rules = default_topology_beta_frontier_governance_rules()
    decisions = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        decisions.extend((
            TopologyBetaFrontierGovernanceDecision("scope", operation, all(item.adapter.source_ids for item in rows), len(rows), "source closure represents declared scope"),
            TopologyBetaFrontierGovernanceDecision("context", operation, all(item.observed_state != "out_of_domain" or "context_mismatch" in item.observed_issue_codes for item in rows), sum(item.observed_state == "out_of_domain" for item in rows), "foreign paths retain a context issue"),
            TopologyBetaFrontierGovernanceDecision("lineage", operation, all(item.adapter.content_address.startswith("sha256:") for item in rows), len(rows), "result addresses are present"),
            TopologyBetaFrontierGovernanceDecision("review", operation, sum(item.role == "control" for item in rows) == 3, sum(item.role == "control" for item in rows), "three controls remain visible"),
        ))
    values = tuple(decisions)
    blocking_rules = {item.rule_id for item in rules if item.blocking}
    failures = tuple(sorted({item.rule_id for item in values if item.rule_id in blocking_rules and not item.passed}))
    return TopologyBetaFrontierGovernanceReport(rules, values, failures, not failures and evaluation.accepted)


__all__ = ["TopologyBetaFrontierGovernanceDecision", "TopologyBetaFrontierGovernanceReport", "TopologyBetaFrontierGovernanceRule", "build_topology_beta_frontier_governance", "default_topology_beta_frontier_governance_rules"]
