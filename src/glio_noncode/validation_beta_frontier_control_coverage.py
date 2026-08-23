"""Control-balance projections."""

from .validation_beta_frontier_governance import ValidationBetaFrontierControlCoverage, ValidationBetaFrontierControlCoverageRow, build_validation_beta_frontier_control_coverage


def validation_beta_frontier_controls_are_balanced(value: ValidationBetaFrontierControlCoverage) -> bool:
    return value.accepted and all(row.total_controls == 3 for row in value.rows)


__all__ = ["ValidationBetaFrontierControlCoverage", "ValidationBetaFrontierControlCoverageRow", "build_validation_beta_frontier_control_coverage", "validation_beta_frontier_controls_are_balanced"]
