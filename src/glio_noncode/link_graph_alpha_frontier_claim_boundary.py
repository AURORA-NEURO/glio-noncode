"""Allowed and blocked claim vocabulary for candidate link outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierClaimRule:
    rule_id: str
    operation: str
    claim: str
    allowed: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierClaimBoundary:
    rules: tuple[LinkGraphAlphaFrontierClaimRule, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def allowed_claims(self, operation: str | None = None) -> tuple[str, ...]:
        return tuple(item.claim for item in self.rules if item.allowed and (operation is None or item.operation == operation))

    def blocked_claims(self, operation: str | None = None) -> tuple[str, ...]:
        return tuple(item.claim for item in self.rules if not item.allowed and (operation is None or item.operation == operation))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rules": [item.to_dict() for item in self.rules], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_claim_boundary() -> LinkGraphAlphaFrontierClaimBoundary:
    rules = []
    for operation in LinkGraphAlphaFrontierOperation:
        rules.extend((LinkGraphAlphaFrontierClaimRule(f"{operation.value}:candidate", operation.value, "candidate evidence path is present", True, "the primitive output is descriptive"), LinkGraphAlphaFrontierClaimRule(f"{operation.value}:mechanism", operation.value, "candidate path proves regulatory mechanism", False, "mechanism requires evidence outside this boundary"), LinkGraphAlphaFrontierClaimRule(f"{operation.value}:target", operation.value, "one gene is the definitive target", False, "alternative genes and uncertainty remain visible")))
    values = tuple(rules)
    return LinkGraphAlphaFrontierClaimBoundary(values, len(values) == 12 and sum(item.allowed for item in values) == 4)


def allowed_link_graph_alpha_frontier_claims(operation: str | None = None) -> tuple[str, ...]:
    return build_link_graph_alpha_frontier_claim_boundary().allowed_claims(operation)


__all__ = ["LinkGraphAlphaFrontierClaimBoundary", "LinkGraphAlphaFrontierClaimRule", "allowed_link_graph_alpha_frontier_claims", "build_link_graph_alpha_frontier_claim_boundary"]
