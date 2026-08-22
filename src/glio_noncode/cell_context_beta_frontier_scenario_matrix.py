"""Scenario grouping that keeps positive and refusal cases separate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierScenario:
    scenario_id: str
    class_name: str
    record_ids: tuple[str, ...]
    expected_states: tuple[str, ...]
    purpose: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.class_name or not self.record_ids or not self.purpose:
            raise ValidationError("beta scenario is incomplete")
        if len(self.record_ids) != len(self.expected_states):
            raise ValidationError("beta scenario IDs and states must align")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierScenarioMatrix:
    scenarios: tuple[CellContextBetaFrontierScenario, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.scenarios) != 4:
            raise ValidationError("beta scenario matrix needs four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_scenario_matrix(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierScenarioMatrix:
    scenarios = []
    for operation in sorted({item.operation for item in evaluation.records}):
        rows = tuple(item for item in evaluation.records if item.operation == operation)
        scenarios.append(
            CellContextBetaFrontierScenario(
                operation,
                "positive-controls",
                tuple(item.record_id for item in rows),
                tuple(item.observed_state for item in rows),
                "positive, parser, ambiguity, and gate paths",
            )
        )
    return CellContextBetaFrontierScenarioMatrix(
        tuple(scenarios),
        len(scenarios) == 4 and all(len(item.record_ids) == 4 for item in scenarios),
    )


def evaluate_cell_context_beta_frontier_scenarios(
    matrix: CellContextBetaFrontierScenarioMatrix,
) -> dict[str, Any]:
    return {
        "accepted": matrix.accepted,
        "scenario_count": len(matrix.scenarios),
        "scenarios": [item.to_dict() for item in matrix.scenarios],
        "content_address": matrix.content_address,
    }


__all__ = [
    "CellContextBetaFrontierScenario",
    "CellContextBetaFrontierScenarioMatrix",
    "build_cell_context_beta_frontier_scenario_matrix",
    "evaluate_cell_context_beta_frontier_scenarios",
]
