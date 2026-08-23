"""Content-addressed release bundle for Domain 12 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_lineage import CohortFoundationLineageGraph
from .cohort_foundation_frontier_metrics import CohortFoundationMetrics
from .cohort_foundation_frontier_policy import CohortFoundationPolicy
from .cohort_foundation_frontier_provenance import CohortFoundationProvenanceGraph
from .cohort_foundation_frontier_public_data import CohortFoundationFixture
from .cohort_foundation_frontier_reconciliation import CohortFoundationReconciliation
from .cohort_foundation_frontier_review import CohortFoundationReviewQueue
from .cohort_foundation_frontier_quality_gate import CohortFoundationQualityGate


@dataclass(frozen=True, slots=True)
class CohortFoundationReleaseBundle:
    bundle_id: str
    fixture: CohortFoundationFixture
    evaluation: CohortFoundationEvaluation
    metrics: CohortFoundationMetrics
    lineage: CohortFoundationLineageGraph
    provenance: CohortFoundationProvenanceGraph
    policy: CohortFoundationPolicy
    reconciliation: CohortFoundationReconciliation
    quality: CohortFoundationQualityGate
    review: CohortFoundationReviewQueue
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def accepted(self) -> bool:
        return self.quality.accepted and self.reconciliation.reconciled and self.provenance.closed


def assemble_cohort_foundation_frontier_bundle(
    fixture: CohortFoundationFixture,
    evaluation: CohortFoundationEvaluation,
    metrics: CohortFoundationMetrics,
    lineage: CohortFoundationLineageGraph,
    provenance: CohortFoundationProvenanceGraph,
    policy: CohortFoundationPolicy,
    reconciliation: CohortFoundationReconciliation,
    quality: CohortFoundationQualityGate,
    review: CohortFoundationReviewQueue,
    *,
    bundle_id: str = "cohort-foundation-frontier-bundle-v1",
) -> CohortFoundationReleaseBundle:
    body = {"bundle_id": bundle_id, "fixture": fixture.content_address, "evaluation": evaluation.content_address, "metrics": metrics.content_address, "lineage": lineage.content_address, "provenance": provenance.content_address, "policy": policy.content_address, "reconciliation": reconciliation.content_address, "quality": quality.content_address, "review": review.content_address}
    return CohortFoundationReleaseBundle(bundle_id, fixture, evaluation, metrics, lineage, provenance, policy, reconciliation, quality, review, content_hash(body))


__all__ = ["CohortFoundationReleaseBundle", "assemble_cohort_foundation_frontier_bundle"]
