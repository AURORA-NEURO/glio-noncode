"""Named scenarios for overlap, proximity, cCRE, and consensus behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierScenario:
    scenario_id: str
    name: str
    record_ids: tuple[str, ...]
    expected_states: tuple[str, ...]
    required_issues: tuple[str, ...]
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierScenarioMatrix:
    scenarios: tuple[LinkGraphFoundationFrontierScenario, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"scenarios": [item.to_dict() for item in self.scenarios], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_foundation_frontier_scenarios() -> tuple[LinkGraphFoundationFrontierScenario, ...]:
    return (LinkGraphFoundationFrontierScenario("positive", "positive baselines", ("D10-C01-P", "D10-C02-P", "D10-C03-P", "D10-C04-P"), ("supported",) * 4, (), "each primitive emits a bounded positive path"), LinkGraphFoundationFrontierScenario("ambiguity", "candidate ambiguity", ("D10-C01-C1", "D10-C02-C1", "D10-C03-C1"), ("ambiguous",) * 3, ("multiple_overlaps", "distance_tie", "multiple_ccres"), "ties and one-to-many assignments remain visible"), LinkGraphFoundationFrontierScenario("absence", "baseline absence", ("D10-C01-C2", "D10-C02-C2", "D10-C03-C2"), ("absent", "abstained", "absent"), ("no_overlap", "distance_window", "no_ccre"), "absence is not transformed into a mechanism claim"), LinkGraphFoundationFrontierScenario("boundary", "context boundary", ("D10-C01-C3", "D10-C02-C3", "D10-C03-C3", "D10-C04-C3"), ("out_of_domain", "abstained", "out_of_domain", "out_of_domain"), ("context_mismatch",), "foreign evidence is gated"), LinkGraphFoundationFrontierScenario("consensus", "evidence aggregation", ("D10-C04-P", "D10-C04-C1", "D10-C04-C2"), ("supported", "partial", "contradictory"), ("single_method", "contradictory_evidence"), "method identity and disagreement remain explicit"))


def build_link_graph_foundation_frontier_scenario_matrix(evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierScenarioMatrix:
    rows = {row.record_id: row for row in evaluation.rows}
    scenarios = default_link_graph_foundation_frontier_scenarios()
    checks = []
    for scenario in scenarios:
        selected = tuple(rows[item] for item in scenario.record_ids if item in rows)
        issues = {code for row in selected for code in row.observed_issue_codes}
        checks.append(check(scenario.scenario_id, tuple(row.observed_state for row in selected) == scenario.expected_states and set(scenario.required_issues) <= issues, scenario.purpose, scenario.record_ids))
    return LinkGraphFoundationFrontierScenarioMatrix(scenarios, tuple(checks), all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierScenario", "LinkGraphFoundationFrontierScenarioMatrix", "build_link_graph_foundation_frontier_scenario_matrix", "default_link_graph_foundation_frontier_scenarios"]
