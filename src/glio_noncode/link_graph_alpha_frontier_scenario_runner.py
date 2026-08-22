"""Execute named scenario slices against an already-replayed evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_scenario_matrix import LinkGraphAlphaFrontierScenario, default_link_graph_alpha_frontier_scenarios
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierScenarioRun:
    scenario_id: str
    record_ids: tuple[str, ...]
    observed_states: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierScenarioRunReport:
    runs: tuple[LinkGraphAlphaFrontierScenarioRun, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def run(self, scenario_id: str) -> LinkGraphAlphaFrontierScenarioRun:
        for item in self.runs:
            if item.scenario_id == scenario_id:
                return item
        raise KeyError(scenario_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"runs": [item.to_dict() for item in self.runs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_alpha_frontier_scenarios(evaluation: LinkGraphAlphaFrontierEvaluation, scenarios: tuple[LinkGraphAlphaFrontierScenario, ...] | None = None) -> LinkGraphAlphaFrontierScenarioRunReport:
    selected = scenarios or default_link_graph_alpha_frontier_scenarios()
    rows = {row.record_id: row for row in evaluation.rows}
    runs = []
    for scenario in selected:
        selected_rows = tuple(rows[record_id] for record_id in scenario.record_ids if record_id in rows)
        states = tuple(row.observed_state for row in selected_rows)
        issues = tuple(sorted({code for row in selected_rows for code in row.observed_issue_codes}))
        accepted = tuple(row.record_id for row in selected_rows) == scenario.record_ids and states == scenario.expected_states and set(scenario.required_issue_codes) <= set(issues)
        runs.append(LinkGraphAlphaFrontierScenarioRun(scenario.scenario_id, scenario.record_ids, states, issues, accepted))
    values = tuple(runs)
    return LinkGraphAlphaFrontierScenarioRunReport(values, bool(values) and all(item.accepted for item in values))


__all__ = ["LinkGraphAlphaFrontierScenarioRun", "LinkGraphAlphaFrontierScenarioRunReport", "run_link_graph_alpha_frontier_scenarios"]
