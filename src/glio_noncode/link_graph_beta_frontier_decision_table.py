"""Decision table making C05-C08 states and issues explicit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDecisionRule:
    rule_id: str
    operation: str
    condition: str
    expected_state: str
    issue_code: str
    record_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDecisionResult:
    rule_id: str
    observed_states: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool

    @property
    def accepted(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDecisionTable:
    fixture_id: str
    rules: tuple[LinkGraphBetaFrontierDecisionRule, ...]
    results: tuple[LinkGraphBetaFrontierDecisionResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_rules(self) -> tuple[str, ...]:
        return tuple(item.rule_id for item in self.results if not item.accepted)

    def rule(self, rule_id: str) -> LinkGraphBetaFrontierDecisionRule:
        return next(item for item in self.rules if item.rule_id == rule_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "rules": [item.to_dict() for item in self.rules], "results": [item.to_dict() for item in self.results], "failed_rules": self.failed_rules, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_decision_table(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierDecisionTable:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    rules = tuple(LinkGraphBetaFrontierDecisionRule(f"rule-{record.record_id.lower()}", record.operation.value, f"fixture record {record.record_id}", record.expected_state, record.expected_issue_codes[0] if record.expected_issue_codes else "none", (record.record_id,)) for record in value.records)
    results = []
    for rule in rules:
        rows = tuple(row for row in replay.rows if row.record_id in rule.record_ids)
        issues = tuple(sorted({issue for row in rows for issue in row.observed_issue_codes}))
        results.append(LinkGraphBetaFrontierDecisionResult(rule.rule_id, tuple(row.observed_state for row in rows), issues, bool(rows) and all(row.observed_state == rule.expected_state for row in rows), rule.issue_code == "none" or rule.issue_code in issues))
    values = tuple(results)
    return LinkGraphBetaFrontierDecisionTable(value.fixture_id, rules, values, bool(values) and all(item.accepted for item in values))


def decision_table_summary(table: LinkGraphBetaFrontierDecisionTable) -> dict[str, Any]:
    return {"fixture_id": table.fixture_id, "rule_count": len(table.rules), "result_count": len(table.results), "passed_count": sum(item.accepted for item in table.results), "failed_rules": table.failed_rules, "accepted": table.accepted}


__all__ = ["LinkGraphBetaFrontierDecisionResult", "LinkGraphBetaFrontierDecisionRule", "LinkGraphBetaFrontierDecisionTable", "build_link_graph_beta_frontier_decision_table", "decision_table_summary"]
