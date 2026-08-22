"""Explicit allowed and excluded claim boundaries for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_bundle import CausalBetaFrontierReleaseBundle
from .causal_beta_frontier_operational import CausalBetaFrontierOperationalMatrix
from .causal_beta_frontier_public_data import CAUSAL_BETA_FRONTIER_BOUNDARY
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierClaimBoundary:
    boundary_id: str
    boundary_kind: str
    statement: str
    enforced: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"boundary_id": self.boundary_id, "boundary_kind": self.boundary_kind, "statement": self.statement, "enforced": self.enforced}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierClaimBoundaryReport:
    fixture_id: str
    boundary: str
    allowed: tuple[CausalBetaFrontierClaimBoundary, ...]
    excluded: tuple[CausalBetaFrontierClaimBoundary, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def all_boundaries(self) -> tuple[CausalBetaFrontierClaimBoundary, ...]:
        return self.allowed + self.excluded

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "boundary": self.boundary, "allowed": [item.to_dict() for item in self.allowed], "excluded": [item.to_dict() for item in self.excluded], "allowed_count": len(self.allowed), "excluded_count": len(self.excluded), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_claim_boundary(bundle: CausalBetaFrontierReleaseBundle, operational: CausalBetaFrontierOperationalMatrix) -> CausalBetaFrontierClaimBoundaryReport:
    allowed = (
        CausalBetaFrontierClaimBoundary("allowed:positive", "allowed", "Use supported public aggregate receipts for bounded method validation.", True),
        CausalBetaFrontierClaimBoundary("allowed:comparison", "allowed", "Compare deterministic state and issue outcomes across the four declared operations.", True),
        CausalBetaFrontierClaimBoundary("allowed:review", "allowed", "Route incomplete or conflicting rows to an explicit review queue.", True),
    )
    excluded = (
        CausalBetaFrontierClaimBoundary("excluded:patient", "excluded", "No patient-level inference or clinical decision is supported.", True),
        CausalBetaFrontierClaimBoundary("excluded:diagnosis", "excluded", "No diagnosis, treatment, or outcome claim is supported.", True),
        CausalBetaFrontierClaimBoundary("excluded:foreign-context", "excluded", "Foreign-context controls cannot be promoted into the release set.", True),
        CausalBetaFrontierClaimBoundary("excluded:unresolved", "excluded", "Quarantined and abstained rows cannot be used as positive evidence.", True),
    )
    accepted = bool(bundle.publishable and operational.accepted and len(allowed) == 3 and len(excluded) == 4 and all(item.enforced for item in allowed + excluded) and bundle.allowed_uses and bundle.excluded_uses)
    return CausalBetaFrontierClaimBoundaryReport(operational.fixture_id, CAUSAL_BETA_FRONTIER_BOUNDARY, allowed, excluded, accepted)


__all__ = ["CausalBetaFrontierClaimBoundary", "CausalBetaFrontierClaimBoundaryReport", "build_causal_beta_frontier_claim_boundary"]
