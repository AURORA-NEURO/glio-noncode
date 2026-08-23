"""Claim ceiling for validation planning outputs."""

from .validation_beta_frontier_governance import ValidationBetaFrontierClaimBoundary, build_validation_beta_frontier_claim_boundary


def validation_beta_frontier_claim_is_allowed(boundary: ValidationBetaFrontierClaimBoundary, claim: str) -> bool:
    return claim in boundary.allowed_claims and claim not in boundary.excluded_claims


__all__ = ["ValidationBetaFrontierClaimBoundary", "build_validation_beta_frontier_claim_boundary", "validation_beta_frontier_claim_is_allowed"]
