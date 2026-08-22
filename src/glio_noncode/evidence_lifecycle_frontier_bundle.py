"""Review bundle assembly for the Domain 14 lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_lineage import EvidenceLifecycleLineageGraph
from .evidence_lifecycle_frontier_metrics import EvidenceLifecycleMetricsReport
from .evidence_lifecycle_frontier_policy import (
    EvidenceLifecyclePolicy,
    EvidenceLifecyclePolicyDecision,
)
from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleFixture
from .evidence_lifecycle_frontier_reconciliation import EvidenceLifecycleReconciliation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReleaseBundle:
    bundle_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    lineage_address: str
    reconciliation_address: str
    policy_id: str
    policy_address: str
    policy_decisions: tuple[EvidenceLifecyclePolicyDecision, ...]
    release_notes: tuple[str, ...]
    content_address: str

    @property
    def publishable(self) -> bool:
        return all(item.publishable for item in self.policy_decisions)

    def __post_init__(self) -> None:
        require_non_empty(self.bundle_id, "bundle_id")
        if not self.release_notes:
            raise ValueError("evidence lifecycle bundle requires notes")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


def assemble_evidence_lifecycle_bundle(fixture: EvidenceLifecycleFixture, evaluation: EvidenceLifecycleEvaluation, metrics: EvidenceLifecycleMetricsReport, lineage: EvidenceLifecycleLineageGraph, reconciliation: EvidenceLifecycleReconciliation, policy: EvidenceLifecyclePolicy, *, bundle_id: str = "evidence-lifecycle-release") -> EvidenceLifecycleReleaseBundle:
    body = {"bundle_id": bundle_id, "fixture_id": fixture.fixture_id, "fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "metrics_address": metrics.content_address, "lineage_address": lineage.content_address, "reconciliation_address": reconciliation.content_address, "policy_id": policy.policy_id, "policy_address": policy.content_address, "policy_decisions": policy.decide(evaluation), "release_notes": ("Aggregate public lifecycle fixture only.", "Citation rows retain quarantine outcomes.", "Graph history retains supersession and disagreement.", "A review bundle is not an experimental or clinical conclusion.")}
    return EvidenceLifecycleReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleReleaseBundle", "assemble_evidence_lifecycle_bundle"]
