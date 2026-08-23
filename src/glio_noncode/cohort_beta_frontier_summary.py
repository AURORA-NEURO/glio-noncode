"""Stable summary view used by CLI and documentation checks."""

from __future__ import annotations

from typing import Any

from .cohort_beta_frontier_assurance import CohortBetaFrontierAssurance
from .cohort_beta_frontier_depth import CohortBetaFrontierDepthAudit
from .cohort_beta_frontier_metrics import CohortBetaFrontierMetrics
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_quality_gate import CohortBetaFrontierQualityGate


def build_cohort_beta_frontier_summary(fixture: CohortBetaFrontierFixture, metrics: CohortBetaFrontierMetrics, quality: CohortBetaFrontierQualityGate, depth: CohortBetaFrontierDepthAudit, assurance: CohortBetaFrontierAssurance) -> dict[str, Any]:
    return {"fixture_id": fixture.fixture_id, "fixture_version": fixture.fixture_version, "context_key": fixture.context_key, "operations": list(fixture.operations), "rows": metrics.total_rows, "accepted_rows": metrics.accepted_rows, "acceptance_percent": metrics.acceptance_percent, "quality_accepted": quality.accepted, "depth_percent": depth.score_percent, "assurance_percent": assurance.assurance_percent, "claim_boundary": fixture.boundary}


__all__ = ["build_cohort_beta_frontier_summary"]
