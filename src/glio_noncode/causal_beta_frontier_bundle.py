"""Content-addressed release bundle for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .causal_beta_frontier_contracts import CausalBetaFrontierContractReport
from .causal_beta_frontier_depth import CausalBetaFrontierDepthAudit
from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_lineage import CausalBetaFrontierLineage
from .causal_beta_frontier_metrics import CausalBetaFrontierMetrics
from .causal_beta_frontier_policy import CausalBetaFrontierPolicy
from .causal_beta_frontier_provenance import CausalBetaFrontierProvenanceGraph
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_quality_gate import CausalBetaFrontierQualityGate
from .causal_beta_frontier_reconciliation import CausalBetaFrontierReconciliation
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue
from .causal_beta_frontier_schema import CausalBetaFrontierSchemaReport
from .serialization import content_hash, jsonable


class CausalBetaFrontierBundleState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReleaseBundle:
    bundle_id: str
    version: str
    state: CausalBetaFrontierBundleState
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
    scenario_address: str
    validation_address: str
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "version": self.version, "state": self.state, "fixture_address": self.fixture_address, "evaluation_address": self.evaluation_address, "metrics_address": self.metrics_address, "contracts_address": self.contracts_address, "schema_address": self.schema_address, "lineage_address": self.lineage_address, "provenance_address": self.provenance_address, "depth_address": self.depth_address, "reconciliation_address": self.reconciliation_address, "policy_address": self.policy_address, "review_address": self.review_address, "quality_gate_address": self.quality_gate_address, "scenario_address": self.scenario_address, "validation_address": self.validation_address, "allowed_uses": self.allowed_uses, "excluded_uses": self.excluded_uses, "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def assemble_causal_beta_frontier_bundle(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, metrics: CausalBetaFrontierMetrics, contracts: CausalBetaFrontierContractReport, schema: CausalBetaFrontierSchemaReport, lineage: CausalBetaFrontierLineage, provenance: CausalBetaFrontierProvenanceGraph, depth: CausalBetaFrontierDepthAudit, reconciliation: CausalBetaFrontierReconciliation, policy: CausalBetaFrontierPolicy, review: CausalBetaFrontierReviewQueue, gate: CausalBetaFrontierQualityGate, scenario: Any, validation: Any, *, bundle_id: str = "causal-beta-frontier-bundle", version: str = "2026.08.d11-c05-c08.v1") -> CausalBetaFrontierReleaseBundle:
    addresses = (fixture.content_address, evaluation.content_address, metrics.content_address, contracts.content_address, schema.content_address, lineage.content_address, provenance.content_address, depth.content_address, reconciliation.content_address, policy.content_address, review.content_address, gate.content_address, scenario.content_address, validation.content_address)
    publishable = bool(gate.accepted and evaluation.accepted and reconciliation.reconciled and review.retained_count == 4 and all(addresses))
    state = CausalBetaFrontierBundleState.READY if publishable else (CausalBetaFrontierBundleState.BLOCKED if gate.blocking_check_ids else CausalBetaFrontierBundleState.REVIEW)
    return CausalBetaFrontierReleaseBundle(bundle_id, version, state, *addresses, ("aggregate evidence review", "method development", "reproducibility testing", "research triage"), ("patient care", "diagnostic determination", "treatment selection", "individual risk scoring", "clinical decision support"), publishable)


__all__ = ["CausalBetaFrontierBundleState", "CausalBetaFrontierReleaseBundle", "assemble_causal_beta_frontier_bundle"]
