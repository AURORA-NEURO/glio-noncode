"""State-distribution projections."""

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation


def validation_beta_frontier_state_distribution(evaluation: ValidationBetaFrontierEvaluation) -> dict[str, int]:
    return dict(sorted((str(key), int(value)) for key, value in evaluation.state_counts.items()))


__all__ = ["validation_beta_frontier_state_distribution"]
