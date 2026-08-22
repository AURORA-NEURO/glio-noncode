"""Quality gate joining all C05-C08 release controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_contracts import CausalBetaFrontierContractReport
from .causal_beta_frontier_depth import CausalBetaFrontierDepthAudit
from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_lineage import CausalBetaFrontierLineage
from .causal_beta_frontier_metrics import CausalBetaFrontierMetrics
from .causal_beta_frontier_policy import CausalBetaFrontierPolicyDecision
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, audit_causal_beta_frontier_data
from .causal_beta_frontier_reconciliation import CausalBetaFrontierReconciliation
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue
from .causal_beta_frontier_schema import CausalBetaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierGateCheck:
    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"check_id": self.check_id, "passed": self.passed, "severity": self.severity, "observed": self.observed, "required": self.required, "detail": self.detail}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierQualityGate:
    gate_id: str
    checks: tuple[CausalBetaFrontierGateCheck, ...]
    accepted: bool
    blocking_check_ids: tuple[str, ...]
    review_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"gate_id": self.gate_id, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted, "blocking_check_ids": self.blocking_check_ids, "review_check_ids": self.review_check_ids, "passed_count": self.passed_count, "failed_count": self.failed_count}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_beta_frontier_quality(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, contracts: CausalBetaFrontierContractReport, schema: CausalBetaFrontierSchemaReport, metrics: CausalBetaFrontierMetrics, lineage: CausalBetaFrontierLineage, reconciliation: CausalBetaFrontierReconciliation, depth: CausalBetaFrontierDepthAudit, review: CausalBetaFrontierReviewQueue, decisions: tuple[CausalBetaFrontierPolicyDecision, ...]) -> CausalBetaFrontierQualityGate:
    audit = audit_causal_beta_frontier_data(fixture)
    raw = (
        ("data-audit", audit.accepted, "blocking", audit.failed_checks, (), "fixture and source checks pass"),
        ("evaluation", evaluation.accepted, "blocking", evaluation.failed_record_ids, (), "all positive and control rows replay"),
        ("contracts", contracts.accepted and len(contracts.contracts) == 4, "blocking", len(contracts.contracts), 4, "four contracts are declared"),
        ("schema", schema.accepted, "blocking", len(schema.fields), 10, "record schema is declared"),
        ("metrics", metrics.accepted and metrics.state_accuracy == 1.0 and metrics.issue_accuracy == 1.0, "blocking", (metrics.state_accuracy, metrics.issue_accuracy), (1.0, 1.0), "replay metrics are exact"),
        ("lineage", lineage.accepted and len(lineage.record_edges) == len(fixture.records), "blocking", len(lineage.record_edges), len(fixture.records), "every row has a result edge"),
        ("depth", depth.accepted, "blocking", depth.failed_check_ids, (), "depth checks pass"),
        ("reconciliation", reconciliation.reconciled, "blocking", reconciliation.mismatch_record_ids, (), "expected and observed floors agree"),
        ("review-coverage", review.accepted and len(review.items) == len(fixture.records), "blocking", len(review.items), len(fixture.records), "every row has a disposition"),
        ("decision-coverage", len(decisions) == len(fixture.records), "blocking", len(decisions), len(fixture.records), "every row has a policy decision"),
        ("positive-retention", review.retained_count == 4, "blocking", review.retained_count, 4, "one positive per operation is retained"),
        ("control-blocking", review.blocked_count >= 8, "review", review.blocked_count, 8, "contradictory and foreign controls remain blocked"),
        ("boundary", fixture.boundary == "public_aggregate_non_patient", "blocking", fixture.boundary, "public_aggregate_non_patient", "clinical boundary is explicit"),
    )
    checks = tuple(CausalBetaFrontierGateCheck(*item) for item in raw)
    blocking = tuple(item.check_id for item in checks if not item.passed and item.severity == "blocking")
    reviews = tuple(item.check_id for item in checks if not item.passed and item.severity == "review")
    return CausalBetaFrontierQualityGate("causal-beta-frontier-quality-gate", checks, not blocking, blocking, reviews)


__all__ = ["CausalBetaFrontierGateCheck", "CausalBetaFrontierQualityGate", "evaluate_causal_beta_frontier_quality"]
