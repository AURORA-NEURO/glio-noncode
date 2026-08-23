"""Allowed and prohibited claims for longitudinal aggregate outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_contracts import CohortAlphaFrontierContractRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierClaimBoundary:
    allowed_claims: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    operation_claims: dict[str, tuple[str, ...]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_claim_boundary(contracts: CohortAlphaFrontierContractRegistry) -> CohortAlphaFrontierClaimBoundary:
    allowed = ("descriptive clonality and timing", "descriptive primary-recurrence frequency", "descriptive treatment-selection signal", "bounded cross-cohort direction concordance")
    prohibited = tuple(sorted({claim for item in contracts.contracts for claim in item.prohibited_claims}))
    operation_claims = {item.operation: (f"descriptive {item.title}", "exact-context aggregate evidence") for item in contracts.contracts}
    return CohortAlphaFrontierClaimBoundary(allowed, prohibited, operation_claims, len(operation_claims) == 4 and bool(prohibited), content_hash({"allowed": allowed, "prohibited": prohibited, "operation_claims": operation_claims}, prefix="alpha-claim-boundary"))


__all__ = ["CohortAlphaFrontierClaimBoundary", "build_cohort_alpha_frontier_claim_boundary"]
