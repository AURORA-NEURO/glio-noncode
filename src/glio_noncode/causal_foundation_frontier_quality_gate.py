"""Release quality gate joining the causal foundation control surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_contracts import CausalFoundationFrontierContractReport
from .causal_foundation_frontier_depth import CausalFoundationFrontierDepthAudit
from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_lineage import CausalFoundationFrontierLineage
from .causal_foundation_frontier_metrics import CausalFoundationFrontierMetrics
from .causal_foundation_frontier_policy import CausalFoundationFrontierPolicyDecision
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture, audit_causal_foundation_frontier_data
from .causal_foundation_frontier_reconciliation import CausalFoundationFrontierReconciliation
from .causal_foundation_frontier_review import CausalFoundationFrontierReviewQueue
from .causal_foundation_frontier_schema import CausalFoundationFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierGateCheck:
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
class CausalFoundationFrontierQualityGate:
    gate_id: str
    checks: tuple[CausalFoundationFrontierGateCheck, ...]
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

    def check(self, check_id: str) -> CausalFoundationFrontierGateCheck:
        return next(item for item in self.checks if item.check_id == check_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"gate_id": self.gate_id, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted, "blocking_check_ids": self.blocking_check_ids, "review_check_ids": self.review_check_ids, "passed_count": self.passed_count, "failed_count": self.failed_count}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_foundation_frontier_quality(
    fixture: CausalFoundationFrontierFixture,
    evaluation: CausalFoundationFrontierEvaluation,
    contracts: CausalFoundationFrontierContractReport,
    schema: CausalFoundationFrontierSchemaReport,
    metrics: CausalFoundationFrontierMetrics,
    lineage: CausalFoundationFrontierLineage,
    reconciliation: CausalFoundationFrontierReconciliation,
    depth: CausalFoundationFrontierDepthAudit,
    review: CausalFoundationFrontierReviewQueue,
    decisions: tuple[CausalFoundationFrontierPolicyDecision, ...],
) -> CausalFoundationFrontierQualityGate:
    audit = audit_causal_foundation_frontier_data(fixture)
    raw = (
        ("data-audit", audit.accepted, "blocking", audit.failed_checks, (), "public aggregate fixture boundary and receipts pass"),
        ("evaluation", evaluation.accepted, "blocking", evaluation.failed_record_ids, (), "all expected state and issue floors reconcile"),
        ("contracts", contracts.accepted, "blocking", len(contracts.contracts), 4, "four operation contracts are closed"),
        ("schema", schema.accepted, "blocking", len(schema.fields), 10, "record envelope schema is declared"),
        ("metrics", metrics.accepted and metrics.state_accuracy == 1.0 and metrics.issue_accuracy == 1.0, "blocking", (metrics.state_accuracy, metrics.issue_accuracy), (1.0, 1.0), "replay metrics are exact"),
        ("lineage", lineage.accepted and len(lineage.record_edges) == len(fixture.records), "blocking", len(lineage.record_edges), len(fixture.records), "every record resolves to a result receipt"),
        ("depth", depth.accepted, "blocking", depth.failed_check_ids, (), "depth surface remains complete"),
        ("reconciliation", reconciliation.reconciled, "blocking", reconciliation.mismatch_record_ids, (), "expected and observed rows agree"),
        ("review-coverage", review.accepted and len(review.items) == len(fixture.records), "blocking", len(review.items), len(fixture.records), "every row has a policy disposition"),
        ("policy-coverage", len(decisions) == len(fixture.records), "blocking", len(decisions), len(fixture.records), "every row receives a policy decision"),
        ("control-retention", review.blocked_count >= 5, "review", review.blocked_count, 5, "contradictory and foreign controls remain blocked"),
        ("positive-retention", review.retained_count == 4, "blocking", review.retained_count, 4, "one supported positive per operation is retained"),
        ("no-patient-boundary", fixture.boundary == "public_aggregate_non_patient", "blocking", fixture.boundary, "public_aggregate_non_patient", "release excludes subject-level and clinical use"),
    )
    checks = tuple(CausalFoundationFrontierGateCheck(check_id, bool(passed), severity, observed, required, detail) for check_id, passed, severity, observed, required, detail in raw)
    blocking = tuple(item.check_id for item in checks if not item.passed and item.severity == "blocking")
    review_ids = tuple(item.check_id for item in checks if not item.passed and item.severity == "review")
    return CausalFoundationFrontierQualityGate("causal-foundation-frontier-quality-gate", checks, not blocking, blocking, review_ids)


__all__ = ["CausalFoundationFrontierGateCheck", "CausalFoundationFrontierQualityGate", "evaluate_causal_foundation_frontier_quality"]
