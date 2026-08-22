"""Content-addressed release bundle for C01-C04 foundation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_foundation_frontier_contracts import CausalFoundationFrontierContractReport
from .causal_foundation_frontier_depth import CausalFoundationFrontierDepthAudit
from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_lineage import CausalFoundationFrontierLineage
from .causal_foundation_frontier_metrics import CausalFoundationFrontierMetrics
from .causal_foundation_frontier_policy import CausalFoundationFrontierPolicy
from .causal_foundation_frontier_provenance import CausalFoundationFrontierProvenanceGraph
from .causal_foundation_frontier_quality_gate import CausalFoundationFrontierQualityGate
from .causal_foundation_frontier_reconciliation import CausalFoundationFrontierReconciliation
from .causal_foundation_frontier_review import CausalFoundationFrontierReviewQueue
from .causal_foundation_frontier_schema import CausalFoundationFrontierSchemaReport
from .causal_foundation_frontier_views import CausalFoundationFrontierReviewView, CausalFoundationFrontierSummaryView
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .serialization import content_hash, jsonable


class CausalFoundationFrontierBundleState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierReleaseBundle:
    bundle_id: str
    version: str
    state: CausalFoundationFrontierBundleState
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    contracts_address: str
    schema_address: str
    lineage_address: str
    provenance_address: str
    depth_address: str
    reconciliation_address: str
    policy_address: str
    review_address: str
    quality_gate_address: str
    review_view_address: str
    summary_view_address: str
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "version": self.version, "state": self.state, "fixture_address": self.fixture_address, "evaluation_address": self.evaluation_address, "metrics_address": self.metrics_address, "contracts_address": self.contracts_address, "schema_address": self.schema_address, "lineage_address": self.lineage_address, "provenance_address": self.provenance_address, "depth_address": self.depth_address, "reconciliation_address": self.reconciliation_address, "policy_address": self.policy_address, "review_address": self.review_address, "quality_gate_address": self.quality_gate_address, "review_view_address": self.review_view_address, "summary_view_address": self.summary_view_address, "allowed_uses": self.allowed_uses, "excluded_uses": self.excluded_uses, "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def assemble_causal_foundation_frontier_bundle(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, metrics: CausalFoundationFrontierMetrics, contracts: CausalFoundationFrontierContractReport, schema: CausalFoundationFrontierSchemaReport, lineage: CausalFoundationFrontierLineage, provenance: CausalFoundationFrontierProvenanceGraph, depth: CausalFoundationFrontierDepthAudit, reconciliation: CausalFoundationFrontierReconciliation, policy: CausalFoundationFrontierPolicy, review: CausalFoundationFrontierReviewQueue, gate: CausalFoundationFrontierQualityGate, review_view: CausalFoundationFrontierReviewView, summary_view: CausalFoundationFrontierSummaryView, *, bundle_id: str = "causal-foundation-frontier-bundle", version: str = "2026.08.d11-c01-c04.v1") -> CausalFoundationFrontierReleaseBundle:
    addresses = (fixture.content_address, evaluation.content_address, metrics.content_address, contracts.content_address, schema.content_address, lineage.content_address, provenance.content_address, depth.content_address, reconciliation.content_address, policy.content_address, review.content_address, gate.content_address, review_view.content_address, summary_view.content_address)
    publishable = bool(gate.accepted and evaluation.accepted and reconciliation.reconciled and review.retained_count == 4 and all(addresses))
    state = CausalFoundationFrontierBundleState.READY if publishable else (CausalFoundationFrontierBundleState.BLOCKED if gate.blocking_check_ids else CausalFoundationFrontierBundleState.REVIEW)
    return CausalFoundationFrontierReleaseBundle(bundle_id, version, state, *addresses, ("aggregate evidence review", "method development", "reproducibility testing", "research triage"), ("patient care", "diagnostic determination", "treatment selection", "individual risk scoring", "clinical decision support"), publishable)


__all__ = ["CausalFoundationFrontierBundleState", "CausalFoundationFrontierReleaseBundle", "assemble_causal_foundation_frontier_bundle"]
