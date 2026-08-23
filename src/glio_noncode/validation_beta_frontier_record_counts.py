"""Record-count projections."""

from typing import Any

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation
from .validation_beta_frontier_public_data import ValidationBetaFrontierFixture


def validation_beta_frontier_record_counts(fixture: ValidationBetaFrontierFixture, evaluation: ValidationBetaFrontierEvaluation | None = None) -> dict[str, Any]:
    return {"sources": len(fixture.sources), "records": len(fixture.records), "positive": len(fixture.positive_records), "controls": len(fixture.control_records), "evaluated": 0 if evaluation is None else len(evaluation.rows), "accepted": 0 if evaluation is None else sum(item.accepted for item in evaluation.rows)}


__all__ = ["validation_beta_frontier_record_counts"]
