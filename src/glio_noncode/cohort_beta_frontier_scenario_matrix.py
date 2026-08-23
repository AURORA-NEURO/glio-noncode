"""Scenario coverage across positive, absent, partial, foreign, and contradictory paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierScenario:
    scenario_id: str
    operation: str
    expected_state: str
    observed_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierScenarioMatrix:
    scenarios: tuple[CohortBetaFrontierScenario, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_scenario_matrix(evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierScenarioMatrix:
    values = tuple(CohortBetaFrontierScenario(f"{row.operation}:{row.record_id}", row.operation, row.expected_state.value, len(row.result), row.accepted, content_hash({"record_id": row.record_id, "state": row.observed_state}, prefix="scenario")) for row in evaluation.rows)
    return CohortBetaFrontierScenarioMatrix(values, len(values) == 16 and all(item.accepted for item in values), content_hash(values, prefix="scenario-matrix"))


__all__ = ["CohortBetaFrontierScenario", "CohortBetaFrontierScenarioMatrix", "build_cohort_beta_frontier_scenario_matrix"]
