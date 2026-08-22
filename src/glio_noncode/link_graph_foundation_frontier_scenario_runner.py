"""Execute named scenario slices against replay results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_scenario_matrix import LinkGraphFoundationFrontierScenario, default_link_graph_foundation_frontier_scenarios
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierScenarioRun:
    scenario_id: str
    observed_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierScenarioRunReport:
    runs: tuple[LinkGraphFoundationFrontierScenarioRun, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"runs": [item.to_dict() for item in self.runs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_foundation_frontier_scenarios(evaluation: LinkGraphFoundationFrontierEvaluation, scenarios: tuple[LinkGraphFoundationFrontierScenario, ...] | None = None) -> LinkGraphFoundationFrontierScenarioRunReport:
    rows = {row.record_id: row for row in evaluation.rows}
    runs = []
    for scenario in scenarios or default_link_graph_foundation_frontier_scenarios():
        selected = tuple(rows[item] for item in scenario.record_ids if item in rows)
        states = tuple(item.observed_state for item in selected)
        issues = tuple(sorted({code for item in selected for code in item.observed_issue_codes}))
        runs.append(LinkGraphFoundationFrontierScenarioRun(scenario.scenario_id, states, issues, tuple(item.record_id for item in selected) == scenario.record_ids and states == scenario.expected_states and set(scenario.required_issues) <= set(issues)))
    values = tuple(runs)
    return LinkGraphFoundationFrontierScenarioRunReport(values, bool(values) and all(item.accepted for item in values))


__all__ = ["LinkGraphFoundationFrontierScenarioRun", "LinkGraphFoundationFrontierScenarioRunReport", "run_link_graph_foundation_frontier_scenarios"]
