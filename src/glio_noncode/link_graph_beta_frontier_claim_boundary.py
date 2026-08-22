"""Explicit claim boundaries for beta aggregate evidence exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_public_data import LINK_GRAPH_BETA_FRONTIER_BOUNDARY
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierClaimBoundary:
    boundary_id: str
    allowed_claims: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    boundary: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"boundary_id": self.boundary_id, "allowed_claims": self.allowed_claims, "prohibited_claims": self.prohibited_claims, "boundary": self.boundary, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_claim_boundary() -> LinkGraphBetaFrontierClaimBoundary:
    allowed = ("public aggregate candidate evidence", "method-specific support", "context-qualified state", "source-addressed replay outcome")
    prohibited = ("causal mechanism", "clinical actionability", "patient-level inference", "preferred target conclusion")
    return LinkGraphBetaFrontierClaimBoundary("d10-c05-c08-claim-boundary", allowed, prohibited, LINK_GRAPH_BETA_FRONTIER_BOUNDARY, True)


__all__ = ["LinkGraphBetaFrontierClaimBoundary", "build_link_graph_beta_frontier_claim_boundary"]
