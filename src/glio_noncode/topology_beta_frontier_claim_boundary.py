"""Explicit allowed outputs and blocked interpretations for beta results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierClaim:
    claim_id: str
    operation: str
    result_state: str
    allowed_statement: str
    blocked_statement: str
    required_receipts: tuple[str, ...]
    uncertainty_fields: tuple[str, ...]
    release_scope: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierClaimBoundaryReport:
    claims: tuple[TopologyBetaFrontierClaim, ...]
    allowed_count: int
    blocked_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyBetaFrontierClaim, ...]:
        return tuple(item for item in self.claims if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"claims": [item.to_dict() for item in self.claims], "allowed_count": self.allowed_count, "blocked_count": self.blocked_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_claim_boundary(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierClaimBoundaryReport:
    statements = {
        "loop_stripe": ("The aggregate contains context-qualified loop or stripe feature evidence.", "The feature evidence proves a regulatory mechanism or clinical effect."),
        "promoter_capture": ("The aggregate contains context-qualified promoter-capture observations.", "The contact observation alone proves enhancer function or target-gene causality."),
        "enhancer_promoter_contact": ("The bounded score summarizes retained contact observations.", "The bounded score is a probability, calibrated likelihood, or causal regulatory effect."),
        "activity_by_contact": ("The product combines the declared activity and contact components.", "The product is a probability, intervention effect, or clinical prediction."),
    }
    claims = tuple(TopologyBetaFrontierClaim(f"claim-{index:02d}", row.operation, row.observed_state, statements[row.operation][0], statements[row.operation][1], ("context_key", "source_ids", "content_address"), ("state", "issue_codes", "evidence_ids", "source_versions"), "aggregate_research") for index, row in enumerate(evaluation.rows, start=1))
    return TopologyBetaFrontierClaimBoundaryReport(claims, len(claims), len(claims), len(claims) == 16 and all(item.required_receipts and item.uncertainty_fields for item in claims))


__all__ = ["TopologyBetaFrontierClaim", "TopologyBetaFrontierClaimBoundaryReport", "build_topology_beta_frontier_claim_boundary"]
