"""Release quality gate combining evidence, controls, and boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierEvaluation
from .causal_alpha_frontier_contracts import CausalAlphaFrontierContractReport
from .causal_alpha_frontier_depth import CausalAlphaFrontierDepthAudit
from .causal_alpha_frontier_lineage import CausalAlphaFrontierLineage
from .causal_alpha_frontier_metrics import CausalAlphaFrontierMetrics
from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision
from .causal_alpha_frontier_reconciliation import CausalAlphaFrontierReconciliation
from .causal_alpha_frontier_review import CausalAlphaFrontierReviewQueue
from .causal_alpha_frontier_schema import CausalAlphaFrontierSchemaReport
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierQualityGate:
    gate_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"gate_id": self.gate_id, "checks": self.checks, "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_alpha_frontier_quality(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierEvaluation, contracts: CausalAlphaFrontierContractReport, schema: CausalAlphaFrontierSchemaReport, metrics: CausalAlphaFrontierMetrics, lineage: CausalAlphaFrontierLineage, reconciliation: CausalAlphaFrontierReconciliation, depth: CausalAlphaFrontierDepthAudit, review: CausalAlphaFrontierReviewQueue, decisions: tuple[CausalAlphaFrontierDecision, ...]) -> CausalAlphaFrontierQualityGate:
    checks = (
        {"check_id": "data-identity", "passed": bool(fixture.content_address), "detail": "fixture is content addressed"},
        {"check_id": "evaluation", "passed": evaluation.accepted, "detail": "all sixteen expected states match"},
        {"check_id": "contracts", "passed": contracts.accepted, "detail": "four operation contracts accepted"},
        {"check_id": "schema", "passed": schema.accepted, "detail": "schema closure accepted"},
        {"check_id": "metrics", "passed": metrics.accepted, "detail": "operation coverage metrics accepted"},
        {"check_id": "lineage", "passed": lineage.accepted, "detail": "lineage graph accepted"},
        {"check_id": "reconciliation", "passed": reconciliation.accepted, "detail": "expected and observed states reconcile"},
        {"check_id": "depth", "passed": depth.accepted, "detail": "implementation depth accepted"},
        {"check_id": "review-coverage", "passed": review.accepted and len(review.items) >= 1, "detail": "non-positive states project to review"},
        {"check_id": "decision-closure", "passed": len(decisions) == 16 and len({item.record_id for item in decisions}) == 16, "detail": "one policy decision per row"},
    )
    checks = tuple({**item, "content_address": content_hash(item)} for item in checks)
    return CausalAlphaFrontierQualityGate("causal-alpha-frontier-quality", checks, all(item["passed"] for item in checks))


__all__ = ["CausalAlphaFrontierQualityGate", "evaluate_causal_alpha_frontier_quality"]
