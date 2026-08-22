"""Independent scenario floors for the topology context release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierScenario:
    scenario_id: str
    name: str
    expected_state: str
    observed_count: int
    minimum_count: int

    @property
    def passed(self) -> bool:
        return self.observed_count >= self.minimum_count

    def to_dict(self) -> dict[str, Any]:
        return (
            jsonable({**self.__dict__, "passed": self.passed})
            if hasattr(self, "__dict__")
            else {
                "scenario_id": self.scenario_id,
                "name": self.name,
                "expected_state": self.expected_state,
                "observed_count": self.observed_count,
                "minimum_count": self.minimum_count,
                "passed": self.passed,
            }
        )


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierScenarioMatrix:
    scenarios: tuple[TopologyContextFrontierScenario, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "scenarios": [item.to_dict() for item in self.scenarios],
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_scenario_matrix(
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierScenarioMatrix:
    scenarios = (
        TopologyContextFrontierScenario(
            "positive-supported",
            "supported positive paths",
            "supported",
            len(evaluation.by_state("supported")),
            4,
        ),
        TopologyContextFrontierScenario(
            "partial-control",
            "partial quality controls",
            "partial",
            len(evaluation.by_state("partial")),
            2,
        ),
        TopologyContextFrontierScenario(
            "ambiguous-control",
            "ambiguous alternatives",
            "ambiguous",
            len(evaluation.by_state("ambiguous")),
            1,
        ),
        TopologyContextFrontierScenario(
            "foreign-control",
            "foreign context controls",
            "out_of_domain",
            len(evaluation.by_state("out_of_domain")),
            3,
        ),
    )
    return TopologyContextFrontierScenarioMatrix(scenarios, all(item.passed for item in scenarios))


def evaluate_topology_context_frontier_scenarios(
    matrix: TopologyContextFrontierScenarioMatrix,
) -> dict[str, Any]:
    return {
        "accepted": matrix.accepted,
        "scenario_count": len(matrix.scenarios),
        "failed_ids": [item.scenario_id for item in matrix.scenarios if not item.passed],
    }


__all__ = [
    "TopologyContextFrontierScenario",
    "TopologyContextFrontierScenarioMatrix",
    "build_topology_context_frontier_scenario_matrix",
    "evaluate_topology_context_frontier_scenarios",
]
