"""Run controlled fixture mutation scenarios and retain their outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, evaluate_topology_alpha_frontier_fixture
from .topology_alpha_frontier_mutations import mutate_topology_alpha_frontier_context, mutate_topology_alpha_frontier_expected_state, mutate_topology_alpha_frontier_issue_floor
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, default_topology_alpha_frontier_fixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierScenarioRun:
    scenario_id: str
    mutation: str
    fixture_address: str
    evaluation_address: str
    accepted: bool
    state_match_count: int
    issue_match_count: int
    failed_record_ids: tuple[str, ...]
    expected_effect: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierScenarioRunReport:
    baseline: TopologyAlphaFrontierEvaluation
    scenarios: tuple[TopologyAlphaFrontierScenarioRun, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def scenario(self, scenario_id: str) -> TopologyAlphaFrontierScenarioRun:
        for item in self.scenarios:
            if item.scenario_id == scenario_id:
                return item
        raise KeyError(scenario_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"baseline": self.baseline.to_dict(), "scenarios": [item.to_dict() for item in self.scenarios], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _run(scenario_id: str, mutation: str, fixture: TopologyAlphaFrontierFixture, mutate: Callable[[TopologyAlphaFrontierFixture], TopologyAlphaFrontierFixture], expected_effect: str) -> TopologyAlphaFrontierScenarioRun:
    mutated = mutate(fixture)
    evaluation = evaluate_topology_alpha_frontier_fixture(mutated)
    return TopologyAlphaFrontierScenarioRun(scenario_id, mutation, mutated.content_address, evaluation.content_address, evaluation.accepted, evaluation.state_match_count, evaluation.issue_match_count, evaluation.failed_record_ids, expected_effect)


def run_topology_alpha_frontier_scenarios(fixture: TopologyAlphaFrontierFixture | None = None) -> TopologyAlphaFrontierScenarioRunReport:
    value = fixture or default_topology_alpha_frontier_fixture()
    baseline = evaluate_topology_alpha_frontier_fixture(value)
    scenarios = (_run("state-drift", "expected_state", value, lambda item: mutate_topology_alpha_frontier_expected_state(item), "replay reports one state mismatch"), _run("issue-drift", "issue_floor", value, lambda item: mutate_topology_alpha_frontier_issue_floor(item), "replay reports one issue mismatch"), _run("context-drift", "context", value, lambda item: mutate_topology_alpha_frontier_context(item), "replay reports an explicit context mismatch"))
    accepted = baseline.accepted and len(scenarios) == 3 and all(item.failed_record_ids for item in scenarios)
    return TopologyAlphaFrontierScenarioRunReport(baseline, scenarios, accepted)


__all__ = ["TopologyAlphaFrontierScenarioRun", "TopologyAlphaFrontierScenarioRunReport", "run_topology_alpha_frontier_scenarios"]
