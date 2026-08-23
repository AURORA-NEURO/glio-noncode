"""State and boundary scenario matrix for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierScenario:
    scenario_id: str
    operation: str
    expected_state: str
    result_key_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierScenarioMatrix:
    scenarios: tuple[CohortAlphaFrontierScenario, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_scenario_matrix(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierScenarioMatrix:
    values = tuple(CohortAlphaFrontierScenario(f"{row.operation}:{row.record_id}", row.operation, row.expected_state.value, len(row.result), row.accepted, content_hash({"record_id": row.record_id, "state": row.observed_state}, prefix="alpha-scenario")) for row in evaluation.rows)
    return CohortAlphaFrontierScenarioMatrix(values, len(values) == 16 and all(item.accepted for item in values), content_hash(values, prefix="alpha-scenarios"))


__all__ = ["CohortAlphaFrontierScenario", "CohortAlphaFrontierScenarioMatrix", "build_cohort_alpha_frontier_scenario_matrix"]
