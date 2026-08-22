"""Scenario matrix for alpha support, ambiguity, missingness, and context gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierScenario:
    scenario_id: str
    name: str
    required_states: tuple[str, ...]
    observed_record_ids: tuple[str, ...]
    observed_states: tuple[str, ...]
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierScenarioMatrix:
    scenarios: tuple[TopologyAlphaFrontierScenario, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def scenario(self, scenario_id: str) -> TopologyAlphaFrontierScenario:
        for item in self.scenarios:
            if item.scenario_id == scenario_id:
                return item
        raise KeyError(scenario_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"scenarios": [item.to_dict() for item in self.scenarios], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_scenario_matrix(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierScenarioMatrix:
    targets = ("supported", "partial", "ambiguous", "out_of_domain")
    scenarios = []
    for index, state in enumerate(targets, start=1):
        rows = tuple(item for item in evaluation.rows if item.observed_state == state)
        scenarios.append(TopologyAlphaFrontierScenario(f"scenario-{index:02d}", f"{state} path", (state,), tuple(item.record_id for item in rows), tuple(item.observed_state for item in rows), bool(rows), f"at least one {state} path is represented"))
    values = tuple(scenarios)
    return TopologyAlphaFrontierScenarioMatrix(values, all(item.passed for item in values))


def evaluate_topology_alpha_frontier_scenarios(matrix: TopologyAlphaFrontierScenarioMatrix) -> dict[str, Any]:
    return {"scenario_count": len(matrix.scenarios), "passed_count": sum(item.passed for item in matrix.scenarios), "accepted": matrix.accepted, "states": {item.name: item.observed_states for item in matrix.scenarios}}


__all__ = ["TopologyAlphaFrontierScenario", "TopologyAlphaFrontierScenarioMatrix", "build_topology_alpha_frontier_scenario_matrix", "evaluate_topology_alpha_frontier_scenarios"]
