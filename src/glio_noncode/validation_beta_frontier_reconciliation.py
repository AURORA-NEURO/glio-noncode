"""Expected-state reconciliation helpers."""

from typing import Any

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation
from .validation_beta_frontier_governance import ValidationBetaFrontierReconciliation, reconcile_validation_beta_frontier
from .validation_beta_frontier_public_data import ValidationBetaFrontierFixture


def validation_beta_frontier_reconciliation_summary(value: ValidationBetaFrontierReconciliation) -> dict[str, Any]:
    return {"fixture_id": value.fixture_id, "reconciled": value.reconciled, "item_count": len(value.items), "mismatch_ids": value.mismatch_ids, "content_address": value.content_address}


__all__ = ["ValidationBetaFrontierReconciliation", "reconcile_validation_beta_frontier", "validation_beta_frontier_reconciliation_summary"]
