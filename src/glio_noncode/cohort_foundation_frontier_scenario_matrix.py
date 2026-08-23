"""Scenario probes for threshold, context, and evidence-state boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationScenario:
    scenario_id: str
    operation: CohortFoundationOperation
    probe: str
    expected_state: str
    record_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationScenarioMatrix:
    matrix_id: str
    scenarios: tuple[CohortFoundationScenario, ...]
    accepted: bool
    content_address: str

    @property
    def review_scenarios(self) -> tuple[CohortFoundationScenario, ...]:
        return tuple(item for item in self.scenarios if item.expected_state != "supported")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_scenario_matrix(evaluation: CohortFoundationEvaluation) -> CohortFoundationScenarioMatrix:
    scenarios = []
    for operation in CohortFoundationOperation:
        executions = tuple(item for item in evaluation.executions if item.operation is operation)
        for state in ("supported", "partial", "absent", "out_of_domain"):
            selected = tuple(item.record_id for item in executions if item.actual_state == state)
            if not selected:
                continue
            body = {"operation": operation, "state": state, "records": selected}
            scenarios.append(CohortFoundationScenario(content_hash((operation.value, state), prefix="scenario"), operation, f"{operation.value}:{state}", state, selected, content_hash(body)))
    body = {"matrix_id": "cohort-foundation-frontier-scenarios", "scenarios": scenarios}
    return CohortFoundationScenarioMatrix(body["matrix_id"], tuple(scenarios), len(scenarios) >= 12, content_hash(body))


__all__ = ["CohortFoundationScenario", "CohortFoundationScenarioMatrix", "build_cohort_foundation_frontier_scenario_matrix"]
