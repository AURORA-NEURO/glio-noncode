"""Allowed and blocked claim vocabulary for baseline link outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierClaimRule:
    rule_id: str
    operation: str
    claim: str
    allowed: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierClaimBoundary:
    rules: tuple[LinkGraphFoundationFrontierClaimRule, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def allowed_claims(self, operation: str | None = None) -> tuple[str, ...]:
        return tuple(item.claim for item in self.rules if item.allowed and (operation is None or item.operation == operation))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rules": [item.to_dict() for item in self.rules], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_claim_boundary() -> LinkGraphFoundationFrontierClaimBoundary:
    rules = tuple(rule for operation in LinkGraphFoundationFrontierOperation for rule in (LinkGraphFoundationFrontierClaimRule(f"{operation.value}:candidate", operation.value, "candidate baseline path is present", True, "primitive output is descriptive"), LinkGraphFoundationFrontierClaimRule(f"{operation.value}:mechanism", operation.value, "baseline proves mechanism", False, "mechanism requires evidence outside this boundary"), LinkGraphFoundationFrontierClaimRule(f"{operation.value}:target", operation.value, "one gene is definitive", False, "alternatives and uncertainty remain visible")))
    return LinkGraphFoundationFrontierClaimBoundary(rules, len(rules) == 12)


def allowed_link_graph_foundation_frontier_claims(operation: str | None = None) -> tuple[str, ...]:
    return build_link_graph_foundation_frontier_claim_boundary().allowed_claims(operation)


__all__ = ["LinkGraphFoundationFrontierClaimBoundary", "LinkGraphFoundationFrontierClaimRule", "allowed_link_graph_foundation_frontier_claims", "build_link_graph_foundation_frontier_claim_boundary"]
