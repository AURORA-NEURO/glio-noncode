"""Scenario coverage across operation, state, and boundary dimensions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationFixture,
    SequenceRegulationOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationScenario:
    scenario_id: str
    operation: str
    role: str
    state: str
    record_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_id or self.record_count < 1:
            raise ValidationError("scenario fields are invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationScenarioReport:
    scenarios: tuple[SequenceRegulationScenario, ...]
    expected_scenario_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise ValidationError("scenario report requires scenarios")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_sequence_regulation_scenarios(
    fixture: SequenceRegulationFixture,
    evaluation: SequenceRegulationEvaluation,
) -> SequenceRegulationScenarioReport:
    scenarios = tuple(
        SequenceRegulationScenario(
            scenario_id=f"scenario:{item.record_id}",
            operation=item.adapter.operation.value,
            role=item.role,
            state=item.observed_state.value,
            record_count=1,
        )
        for item in evaluation.records
    )
    operations = {scenario.operation for scenario in scenarios}
    expected = len(fixture.records)
    accepted = len(scenarios) == expected and operations == {
        operation.value for operation in SequenceRegulationOperation
    }
    return SequenceRegulationScenarioReport(scenarios, expected, accepted)


__all__ = [
    "SequenceRegulationScenario",
    "SequenceRegulationScenarioReport",
    "evaluate_sequence_regulation_scenarios",
]
