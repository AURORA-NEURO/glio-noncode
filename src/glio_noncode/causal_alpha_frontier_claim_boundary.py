"""Allowed and excluded claim boundaries for the alpha evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_bundle import CausalAlphaFrontierReleaseBundle
from .causal_alpha_frontier_operational import CausalAlphaFrontierOperationalMatrix
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierClaimBoundaryReport:
    bundle_id: str
    boundary: str
    allowed_claims: tuple[str, ...]
    excluded_claims: tuple[str, ...]
    violation_codes: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"bundle_id": self.bundle_id, "boundary": self.boundary, "allowed_claims": self.allowed_claims, "excluded_claims": self.excluded_claims, "violation_codes": self.violation_codes, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_claim_boundary(bundle: CausalAlphaFrontierReleaseBundle, operational: CausalAlphaFrontierOperationalMatrix) -> CausalAlphaFrontierClaimBoundaryReport:
    allowed = ("descriptive aggregate evidence", "source-omission sensitivity", "confounder checklist status", "dependence-group summary", "negative-control review")
    excluded = ("causal identification", "clinical diagnosis", "treatment recommendation", "prognosis", "patient care")
    violations: list[str] = []
    if not operational.accepted:
        violations.append("operational_matrix_not_accepted")
    if any("causal identification" not in item.excluded_claims for item in bundle.decisions):
        violations.append("unbounded_causal_language")
    return CausalAlphaFrontierClaimBoundaryReport(bundle.bundle_id, "public_aggregate_non_patient", allowed, excluded, tuple(sorted(violations)), not violations)


__all__ = ["CausalAlphaFrontierClaimBoundaryReport", "build_causal_alpha_frontier_claim_boundary"]
