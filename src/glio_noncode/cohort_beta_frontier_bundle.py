"""Content-addressed bundle assembly for a C05-C08 release candidate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_lineage import CohortBetaFrontierLineage
from .cohort_beta_frontier_metrics import CohortBetaFrontierMetrics
from .cohort_beta_frontier_policy import CohortBetaFrontierPolicy
from .cohort_beta_frontier_provenance import CohortBetaFrontierProvenanceGraph
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_quality_gate import CohortBetaFrontierQualityGate
from .cohort_beta_frontier_reconciliation import CohortBetaFrontierReconciliation
from .cohort_beta_frontier_review import CohortBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReleaseBundle:
    bundle_id: str
    fixture_id: str
    evaluation_address: str
    metrics_address: str
    lineage_address: str
    provenance_address: str
    policy_address: str
    reconciliation_address: str
    quality_address: str
    review_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_cohort_beta_frontier_bundle(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, metrics: CohortBetaFrontierMetrics, lineage: CohortBetaFrontierLineage, provenance: CohortBetaFrontierProvenanceGraph, policy: CohortBetaFrontierPolicy, reconciliation: CohortBetaFrontierReconciliation, quality: CohortBetaFrontierQualityGate, review: CohortBetaFrontierReviewQueue) -> CohortBetaFrontierReleaseBundle:
    body = {"bundle_id": "cohort-beta-frontier-c05-c08-bundle", "fixture_id": fixture.fixture_id, "evaluation": evaluation.content_address, "metrics": metrics.content_address, "lineage": lineage.content_address, "provenance": provenance.content_address, "policy": policy.content_address, "reconciliation": reconciliation.content_address, "quality": quality.content_address, "review": review.content_address, "accepted": quality.accepted and reconciliation.reconciled}
    return CohortBetaFrontierReleaseBundle(body["bundle_id"], fixture.fixture_id, evaluation.content_address, metrics.content_address, lineage.content_address, provenance.content_address, policy.content_address, reconciliation.content_address, quality.content_address, review.content_address, body["accepted"], content_hash(body, prefix="bundle"))


__all__ = ["CohortBetaFrontierReleaseBundle", "assemble_cohort_beta_frontier_bundle"]
