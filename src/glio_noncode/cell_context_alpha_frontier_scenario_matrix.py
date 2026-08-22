"""Positive, malformed, ambiguity, delta, and refusal scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierScenario:
    scenario_id: str
    operation: str
    record_ids: tuple[str, ...]
    observed_states: tuple[str, ...]
    purpose: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierScenarioMatrix:
    scenarios: tuple[CellContextAlphaFrontierScenario, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.scenarios) != 4:
            raise ValueError("alpha scenario matrix requires four operations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_scenario_matrix(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierScenarioMatrix:
    scenarios = []
    for operation in sorted({item.operation for item in evaluation.records}):
        rows = tuple(item for item in evaluation.records if item.operation == operation)
        scenarios.append(
            CellContextAlphaFrontierScenario(
                operation,
                operation,
                tuple(item.record_id for item in rows),
                tuple(item.observed_state for item in rows),
                "positive and operation-specific controls",
            )
        )
    return CellContextAlphaFrontierScenarioMatrix(
        tuple(scenarios), all(len(item.record_ids) == 4 for item in scenarios)
    )


def evaluate_cell_context_alpha_frontier_scenarios(
    matrix: CellContextAlphaFrontierScenarioMatrix,
) -> dict[str, Any]:
    return {
        "accepted": matrix.accepted,
        "scenario_count": len(matrix.scenarios),
        "scenarios": [item.to_dict() for item in matrix.scenarios],
        "content_address": matrix.content_address,
    }


__all__ = [
    "CellContextAlphaFrontierScenario",
    "CellContextAlphaFrontierScenarioMatrix",
    "build_cell_context_alpha_frontier_scenario_matrix",
    "evaluate_cell_context_alpha_frontier_scenarios",
]
