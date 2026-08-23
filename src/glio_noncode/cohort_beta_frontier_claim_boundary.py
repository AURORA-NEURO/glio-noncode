"""Allowed claims and explicit ceilings for C05-C08 outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_contracts import CohortBetaFrontierContractRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierClaimBoundary:
    allowed_claims: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    operation_claims: dict[str, tuple[str, ...]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_claim_boundary(contracts: CohortBetaFrontierContractRegistry) -> CohortBetaFrontierClaimBoundary:
    operation_claims = {item.operation: (f"descriptive {item.title} summary", "exact-context aggregate evidence") for item in contracts.contracts}
    prohibited = tuple(sorted({claim for item in contracts.contracts for claim in item.prohibited_claims}))
    allowed = ("descriptive recurrence", "callable-space burden", "bounded functional convergence", "bounded pathway or regulon convergence")
    body = {"allowed": allowed, "prohibited": prohibited, "operation_claims": operation_claims}
    return CohortBetaFrontierClaimBoundary(allowed, prohibited, operation_claims, len(operation_claims) == 4 and bool(prohibited), content_hash(body, prefix="claim-boundary"))


__all__ = ["CohortBetaFrontierClaimBoundary", "build_cohort_beta_frontier_claim_boundary"]
