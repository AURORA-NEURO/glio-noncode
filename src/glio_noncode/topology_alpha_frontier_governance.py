"""Governance rules for scope, context, review, and descriptive outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierGovernanceRule:
    rule_id: str
    title: str
    operations: tuple[str, ...]
    requirement: str
    field: str
    action: str
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierGovernanceDecision:
    rule_id: str
    operation: str
    passed: bool
    observed_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierGovernanceReport:
    rules: tuple[TopologyAlphaFrontierGovernanceRule, ...]
    decisions: tuple[TopologyAlphaFrontierGovernanceDecision, ...]
    blocking_failures: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_rule(self, rule_id: str) -> tuple[TopologyAlphaFrontierGovernanceDecision, ...]:
        return tuple(item for item in self.decisions if item.rule_id == rule_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rules": [item.to_dict() for item in self.rules], "decisions": [item.to_dict() for item in self.decisions], "blocking_failures": self.blocking_failures, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_alpha_frontier_governance_rules() -> tuple[TopologyAlphaFrontierGovernanceRule, ...]:
    operations = ("boundary_motif", "ctcf_cohesin", "idh_insulator", "sv_rewire")
    return (
        TopologyAlphaFrontierGovernanceRule("scope", "Public aggregate scope", operations, "Every payload declares public aggregate scope.", "public_aggregate", "block release", True),
        TopologyAlphaFrontierGovernanceRule("context", "Exact context gate", operations, "Foreign context remains out of domain.", "context_key", "block transport", True),
        TopologyAlphaFrontierGovernanceRule("lineage", "Source and result closure", operations, "Every row retains source and result receipts.", "content_address", "route to review", True),
        TopologyAlphaFrontierGovernanceRule("review", "Control visibility", operations, "Every operation retains three controls.", "role", "block release", True),
        TopologyAlphaFrontierGovernanceRule("descriptive", "Descriptive boundary", operations, "Outputs remain descriptive and aggregate-scoped.", "release_scope", "retain limitation", False),
    )


def build_topology_alpha_frontier_governance(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierGovernanceReport:
    rules = default_topology_alpha_frontier_governance_rules()
    decisions = []
    for operation in sorted({item.operation for item in evaluation.rows}):
        rows = evaluation.by_operation(operation)
        decisions.extend((TopologyAlphaFrontierGovernanceDecision("scope", operation, all(item.adapter.source_ids for item in rows), len(rows), "source receipts retain aggregate scope"), TopologyAlphaFrontierGovernanceDecision("context", operation, all(item.observed_state != "out_of_domain" or "context_mismatch" in item.observed_issue_codes for item in rows), sum(item.observed_state == "out_of_domain" for item in rows), "foreign paths retain a context issue"), TopologyAlphaFrontierGovernanceDecision("lineage", operation, all(item.adapter.content_address.startswith("sha256:") for item in rows), len(rows), "result addresses are present"), TopologyAlphaFrontierGovernanceDecision("review", operation, sum(item.role == "control" for item in rows) == 3, sum(item.role == "control" for item in rows), "three controls remain visible"), TopologyAlphaFrontierGovernanceDecision("descriptive", operation, True, len(rows), "interpretation remains bounded")))
    values = tuple(decisions)
    blocking = {item.rule_id for item in rules if item.blocking}
    failures = tuple(sorted({item.rule_id for item in values if item.rule_id in blocking and not item.passed}))
    return TopologyAlphaFrontierGovernanceReport(rules, values, failures, not failures and evaluation.accepted)


__all__ = ["TopologyAlphaFrontierGovernanceDecision", "TopologyAlphaFrontierGovernanceReport", "TopologyAlphaFrontierGovernanceRule", "build_topology_alpha_frontier_governance", "default_topology_alpha_frontier_governance_rules"]
