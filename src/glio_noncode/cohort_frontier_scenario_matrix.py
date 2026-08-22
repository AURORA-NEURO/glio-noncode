"""Boundary probes for subgroup, transport, federated, and discovery paths."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from .cohort_frontier_public_data import CohortFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierScenario:
    scenario_id: str
    operation: CohortFrontierOperation
    overlap: float
    shift: float
    parity_gap: float
    privacy_floor: int
    evidence_count: int
    expected_review: bool
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.rationale, "rationale")
        if not 0 <= self.overlap <= 1 or not 0 <= self.parity_gap <= 1 or self.shift < 0 or self.privacy_floor < 1 or self.evidence_count < 0:
            raise ValueError("cohort scenario values are out of range")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierScenarioMatrix:
    scenarios: tuple[CohortFrontierScenario, ...]
    dimensions: tuple[str, ...]
    content_address: str

    @property
    def review_scenarios(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.scenarios if item.expected_review)

    @property
    def supported_scenarios(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.scenarios if not item.expected_review)

    def by_operation(self, operation: CohortFrontierOperation) -> tuple[CohortFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"review_scenarios": list(self.review_scenarios), "supported_scenarios": list(self.supported_scenarios)}


def build_cohort_frontier_scenario_matrix() -> CohortFrontierScenarioMatrix:
    rows: list[dict[str, Any]] = []
    index = 0
    for overlap, shift, parity_gap in product((0.50, 0.75, 1.0), (0.10, 0.25, 0.80), (0.10, 0.20, 0.60)):
        index += 1
        rows.append({"scenario_id": f"cohort-scenario-{index:03d}", "operation": CohortFrontierOperation.TRANSPORTABILITY, "overlap": overlap, "shift": shift, "parity_gap": parity_gap, "privacy_floor": 5, "evidence_count": 2, "expected_review": overlap < 0.75 or shift > 0.25, "rationale": "overlap and source-target shift boundaries remain visible"})
    for operation, overlap, shift, parity_gap, privacy_floor, evidence_count, review in ((CohortFrontierOperation.SUBGROUP_FAIRNESS, 1.0, 0.1, 0.1, 5, 2, False), (CohortFrontierOperation.SUBGROUP_FAIRNESS, 1.0, 0.1, 0.6, 5, 2, True), (CohortFrontierOperation.FEDERATED_SUMMARY, 1.0, 0.1, 0.1, 5, 2, False), (CohortFrontierOperation.FEDERATED_SUMMARY, 1.0, 0.1, 0.1, 20, 1, True), (CohortFrontierOperation.COHORT_DISCOVERY, 1.0, 0.1, 0.1, 5, 0, True), (CohortFrontierOperation.COHORT_DISCOVERY, 1.0, 0.1, 0.1, 5, 2, False)):
        index += 1
        rows.append({"scenario_id": f"cohort-scenario-{index:03d}", "operation": operation, "overlap": overlap, "shift": shift, "parity_gap": parity_gap, "privacy_floor": privacy_floor, "evidence_count": evidence_count, "expected_review": review, "rationale": "cohort evidence sufficiency remains separate from clinical interpretation"})
    scenarios = tuple(CohortFrontierScenario(**row, content_address=content_hash(row)) for row in rows)
    body = {"scenarios": scenarios, "dimensions": ("overlap", "shift", "parity_gap", "privacy_floor", "evidence_count", "operation")}
    return CohortFrontierScenarioMatrix(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierScenario", "CohortFrontierScenarioMatrix", "build_cohort_frontier_scenario_matrix"]
