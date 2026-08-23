"""Scenario matrix projections."""

from typing import Any

from .validation_beta_frontier_governance import ValidationBetaFrontierScenario, ValidationBetaFrontierScenarioMatrix, build_validation_beta_frontier_scenario_matrix


def validation_beta_frontier_scenario_counts(matrix: ValidationBetaFrontierScenarioMatrix) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in matrix.scenarios:
        counts[item.state] = counts.get(item.state, 0) + 1
    return counts


__all__ = ["ValidationBetaFrontierScenario", "ValidationBetaFrontierScenarioMatrix", "build_validation_beta_frontier_scenario_matrix", "validation_beta_frontier_scenario_counts"]
