"""Immutable release bundle for the alpha frontier evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_contracts import CausalAlphaFrontierContractReport
from .causal_alpha_frontier_depth import CausalAlphaFrontierDepthAudit
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_lineage import CausalAlphaFrontierLineage
from .causal_alpha_frontier_metrics import CausalAlphaFrontierMetrics
from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision, CausalAlphaFrontierPolicy
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .causal_alpha_frontier_quality_gate import CausalAlphaFrontierQualityGate
from .causal_alpha_frontier_reconciliation import CausalAlphaFrontierReconciliation
from .causal_alpha_frontier_review import CausalAlphaFrontierReviewQueue
from .causal_alpha_frontier_schema import CausalAlphaFrontierSchemaReport
from .causal_alpha_frontier_scenario_matrix import CausalAlphaFrontierScenarioMatrix
from .causal_alpha_frontier_validation_matrix import CausalAlphaFrontierValidationMatrix
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierReleaseBundle:
    bundle_id: str
    fixture: CausalAlphaFrontierFixture
    evaluation: CausalAlphaFrontierFixtureEvaluation
    metrics: CausalAlphaFrontierMetrics
    contracts: CausalAlphaFrontierContractReport
    schema: CausalAlphaFrontierSchemaReport
    lineage: CausalAlphaFrontierLineage
    depth: CausalAlphaFrontierDepthAudit
    reconciliation: CausalAlphaFrontierReconciliation
    policy: CausalAlphaFrontierPolicy
    decisions: tuple[CausalAlphaFrontierDecision, ...]
    review: CausalAlphaFrontierReviewQueue
    quality: CausalAlphaFrontierQualityGate
    scenario: CausalAlphaFrontierScenarioMatrix
    validation: CausalAlphaFrontierValidationMatrix
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "fixture": self.fixture.to_dict(), "evaluation": self.evaluation.to_dict(), "metrics": self.metrics.to_dict(), "contracts": self.contracts.to_dict(), "schema": self.schema.to_dict(), "lineage": self.lineage.to_dict(), "depth": self.depth.to_dict(), "reconciliation": self.reconciliation.to_dict(), "policy": self.policy.to_dict(), "decisions": [item.to_dict() for item in self.decisions], "review": self.review.to_dict(), "quality": self.quality.to_dict(), "scenario": self.scenario.to_dict(), "validation": self.validation.to_dict(), "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def assemble_causal_alpha_frontier_bundle(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, metrics: CausalAlphaFrontierMetrics, contracts: CausalAlphaFrontierContractReport, schema: CausalAlphaFrontierSchemaReport, lineage: CausalAlphaFrontierLineage, depth: CausalAlphaFrontierDepthAudit, reconciliation: CausalAlphaFrontierReconciliation, policy: CausalAlphaFrontierPolicy, decisions: tuple[CausalAlphaFrontierDecision, ...], review: CausalAlphaFrontierReviewQueue, quality: CausalAlphaFrontierQualityGate, scenario: CausalAlphaFrontierScenarioMatrix, validation: CausalAlphaFrontierValidationMatrix, *, bundle_id: str = "causal-alpha-frontier-bundle") -> CausalAlphaFrontierReleaseBundle:
    publishable = bool(quality.accepted and validation.accepted and scenario.accepted and policy.accepted)
    return CausalAlphaFrontierReleaseBundle(bundle_id, fixture, evaluation, metrics, contracts, schema, lineage, depth, reconciliation, policy, decisions, review, quality, scenario, validation, publishable)


__all__ = ["CausalAlphaFrontierReleaseBundle", "assemble_causal_alpha_frontier_bundle"]
