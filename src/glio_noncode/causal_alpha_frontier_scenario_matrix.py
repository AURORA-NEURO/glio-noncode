"""Scenario matrix covering positive and negative control paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture, CausalAlphaFrontierOperation
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierScenario:
    scenario_id: str
    record_id: str
    operation: CausalAlphaFrontierOperation
    role: str
    context_class: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"scenario_id": self.scenario_id, "record_id": self.record_id, "operation": self.operation, "role": self.role, "context_class": self.context_class, "expected_state": self.expected_state, "observed_state": self.observed_state, "expected_issue_codes": self.expected_issue_codes, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierScenarioMatrix:
    fixture_id: str
    scenarios: tuple[CausalAlphaFrontierScenario, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: CausalAlphaFrontierOperation | str) -> tuple[CausalAlphaFrontierScenario, ...]:
        value = CausalAlphaFrontierOperation(str(operation))
        return tuple(item for item in self.scenarios if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "scenarios": [item.to_dict() for item in self.scenarios], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_scenario_matrix(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation) -> CausalAlphaFrontierScenarioMatrix:
    records = fixture.record_map()
    scenarios: list[CausalAlphaFrontierScenario] = []
    for row in evaluation.evaluation.results:
        record = records[row.record_id]
        context_class = "foreign" if record.context_key == fixture.foreign_context_key else "exact"
        scenarios.append(CausalAlphaFrontierScenario(f"scenario:{row.record_id}", row.record_id, row.operation, record.role.value, context_class, row.expected_state.value, row.observed_state.value, row.expected_issue_codes, row.accepted))
    return CausalAlphaFrontierScenarioMatrix(fixture.fixture_id, tuple(scenarios), len(scenarios) == 16 and all(item.accepted for item in scenarios))


__all__ = ["CausalAlphaFrontierScenario", "CausalAlphaFrontierScenarioMatrix", "build_causal_alpha_frontier_scenario_matrix"]
