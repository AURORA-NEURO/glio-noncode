"""Scenario matrix for threshold, evidence, and failure-mode coverage."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from .causal_frontier_public_data import CausalFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierScenario:
    scenario_id: str
    operation: CausalFrontierOperation
    label: str
    minimum_score: float
    maximum_uncertainty: float
    minimum_support: float
    evidence_count: int
    expected_review: bool
    rationale: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.label, "label")
        require_non_empty(self.rationale, "rationale")
        if not 0 <= self.minimum_score <= 1 or not 0 <= self.minimum_support <= 1:
            raise ValueError("scenario thresholds must be bounded")
        if self.maximum_uncertainty < 0 or self.evidence_count < 0:
            raise ValueError("scenario uncertainty and evidence count must be nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierScenarioMatrix:
    scenarios: tuple[CausalFrontierScenario, ...]
    dimensions: tuple[str, ...]
    content_address: str

    @property
    def review_scenarios(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.scenarios if item.expected_review)

    @property
    def publishable_scenarios(self) -> tuple[str, ...]:
        return tuple(item.scenario_id for item in self.scenarios if not item.expected_review)

    def by_operation(self, operation: CausalFrontierOperation) -> tuple[CausalFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "review_scenarios": list(self.review_scenarios),
            "publishable_scenarios": list(self.publishable_scenarios),
        }


def build_causal_frontier_scenario_matrix() -> CausalFrontierScenarioMatrix:
    rows: list[dict[str, Any]] = []
    score_values = (0.45, 0.60, 0.85)
    uncertainty_values = (0.10, 0.25, 0.60)
    support_values = (0.10, 0.20, 0.80)
    index = 0
    for score, uncertainty, support in product(score_values, uncertainty_values, support_values):
        index += 1
        review = score < 0.6 or uncertainty > 0.25 or support < 0.2
        rows.append({
            "scenario_id": f"matrix-{index:03d}",
            "operation": CausalFrontierOperation.SELECTIVE_PREDICTION,
            "label": f"score-{score:.2f}-uncertainty-{uncertainty:.2f}-support-{support:.2f}",
            "minimum_score": 0.6,
            "maximum_uncertainty": 0.25,
            "minimum_support": support,
            "evidence_count": 2 if support >= 0.2 else 1,
            "expected_review": review,
            "rationale": "review is retained when score, uncertainty, or support crosses its declared boundary",
        })
    for operation, label, evidence_count, review in (
        (CausalFrontierOperation.POSTERIOR_DECOMPOSITION, "zero-mass", 0, True),
        (CausalFrontierOperation.POSTERIOR_DECOMPOSITION, "independent-components", 2, False),
        (CausalFrontierOperation.DRIVER_POSTERIOR, "low-support", 1, True),
        (CausalFrontierOperation.DRIVER_POSTERIOR, "multi-source", 3, False),
        (CausalFrontierOperation.DOSSIER_PUBLICATION, "missing-address", 0, True),
        (CausalFrontierOperation.DOSSIER_PUBLICATION, "addressed", 3, False),
    ):
        index += 1
        rows.append({
            "scenario_id": f"matrix-{index:03d}",
            "operation": operation,
            "label": label,
            "minimum_score": 0.6,
            "maximum_uncertainty": 0.25,
            "minimum_support": 0.2,
            "evidence_count": evidence_count,
            "expected_review": review,
            "rationale": "scenario distinguishes evidence sufficiency from a causal conclusion",
        })
    scenarios = tuple(
        CausalFrontierScenario(**row, content_address=content_hash(row)) for row in rows
    )
    body = {
        "scenarios": scenarios,
        "dimensions": ("score", "uncertainty", "support", "evidence_count", "operation"),
    }
    return CausalFrontierScenarioMatrix(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierScenario", "CausalFrontierScenarioMatrix", "build_causal_frontier_scenario_matrix"]
