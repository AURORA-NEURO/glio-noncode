"""Scenario matrix for accepted, boundary, malformed, and review states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


@dataclass(frozen=True, slots=True)
class GammaFrontierScenario:
    """One scenario declaration."""

    scenario_id: str
    operation: GammaFrontierOperation
    dimension: str
    input_state: str
    expected_state: str
    expected_issue: str | None
    visibility: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierScenarioMatrix:
    """Scenario matrix with dimension and operation lookup."""

    scenarios: tuple[GammaFrontierScenario, ...]
    content_address: str

    def by_operation(self, operation: GammaFrontierOperation) -> tuple[GammaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.operation is operation)

    def by_dimension(self, dimension: str) -> tuple[GammaFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.dimension == dimension)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "scenario_count": len(self.scenarios),
            "dimensions": sorted({item.dimension for item in self.scenarios}),
        }


def _scenario(
    index: int,
    operation: GammaFrontierOperation,
    dimension: str,
    input_state: str,
    expected_state: str,
    issue: str | None,
    visibility: str,
    detail: str,
) -> GammaFrontierScenario:
    body = {
        "scenario_id": f"gamma-scenario-{index:03d}",
        "operation": operation,
        "dimension": dimension,
        "input_state": input_state,
        "expected_state": expected_state,
        "expected_issue": issue,
        "visibility": visibility,
        "detail": detail,
    }
    return GammaFrontierScenario(**body, content_address=content_hash(body, prefix="scenario"))


def build_gamma_frontier_scenario_matrix() -> GammaFrontierScenarioMatrix:
    """Return 20 scenarios spanning all four surfaces."""

    rows = []
    index = 1
    dimensions = (
        ("accepted", "valid", "ready_for_review", None, "visible", "valid in-context input"),
        (
            "foreign_context",
            "foreign",
            "out_of_domain",
            "context_mismatch",
            "visible",
            "foreign context is retained",
        ),
        (
            "malformed",
            "malformed",
            "abstained",
            "invalid_surface_input",
            "visible",
            "malformed input is retained",
        ),
        (
            "boundary",
            "bounded",
            "review_required",
            None,
            "visible",
            "bounded input may need review",
        ),
        ("replay", "repeated", "stable", None, "visible", "repeated input has stable addresses"),
    )
    for operation in GammaFrontierOperation:
        for dimension, input_state, expected_state, issue, visibility, detail in dimensions:
            rows.append(
                _scenario(
                    index,
                    operation,
                    dimension,
                    input_state,
                    expected_state,
                    issue,
                    visibility,
                    detail,
                )
            )
            index += 1
    body = {"scenarios": tuple(rows)}
    return GammaFrontierScenarioMatrix(
        scenarios=tuple(rows), content_address=content_hash(body, prefix="scenario-matrix")
    )


__all__ = [
    "GammaFrontierScenario",
    "GammaFrontierScenarioMatrix",
    "build_gamma_frontier_scenario_matrix",
]
