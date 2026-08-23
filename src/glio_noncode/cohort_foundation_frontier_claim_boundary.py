"""Explicit allowed and prohibited claims for C01-C04 outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_contracts import CohortFoundationContractRegistry


@dataclass(frozen=True, slots=True)
class CohortFoundationClaimBoundary:
    boundary_id: str
    allowed_claims: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    operation_prohibited_claims: dict[str, tuple[str, ...]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_claim_boundary(contracts: CohortFoundationContractRegistry) -> CohortFoundationClaimBoundary:
    operation_claims = {item.operation.value: item.prohibited_claims for item in contracts.contracts}
    prohibited = tuple(sorted({claim for values in operation_claims.values() for claim in values}))
    allowed = ("the aggregate record was evaluated", "the declared context matched or failed", "the descriptive control state", "the source and content receipts", "the review or quarantine disposition")
    body = {"allowed": allowed, "prohibited": prohibited, "operations": operation_claims}
    return CohortFoundationClaimBoundary("cohort-foundation-frontier-claim-boundary", allowed, prohibited, operation_claims, bool(operation_claims) and bool(prohibited), content_hash(body))


__all__ = ["CohortFoundationClaimBoundary", "build_cohort_foundation_frontier_claim_boundary"]
