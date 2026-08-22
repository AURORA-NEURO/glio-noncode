"""Explicit risks, mitigations, and residual boundaries for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRisk:
    risk_id: str
    title: str
    likelihood: str
    impact: str
    mitigation: str
    residual_boundary: str
    blocking: bool

    @property
    def rating(self) -> str:
        if self.likelihood == "high" and self.impact == "high":
            return "critical"
        if self.impact == "high" or self.likelihood == "high":
            return "elevated"
        return "managed"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRiskRegister:
    risks: tuple[LinkGraphFoundationFrontierRisk, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_risks(self) -> tuple[str, ...]:
        return tuple(item.risk_id for item in self.risks if item.blocking)

    def by_rating(self, rating: str) -> tuple[LinkGraphFoundationFrontierRisk, ...]:
        return tuple(item for item in self.risks if item.rating == rating)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"risks": [item.to_dict() for item in self.risks], "blocking_risks": self.blocking_risks, "rating_counts": {rating: len(self.by_rating(rating)) for rating in ("critical", "elevated", "managed")}, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_risk_register() -> LinkGraphFoundationFrontierRiskRegister:
    risks = (LinkGraphFoundationFrontierRisk("risk-context-drift", "reference context drift", "medium", "high", "require context keys on every record and replay result", "public aggregate context does not represent a patient cohort", False), LinkGraphFoundationFrontierRisk("risk-nearest-baseline", "nearest gene overinterpretation", "medium", "high", "retain distance windows and ties as explicit abstention", "nearest proximity is not causal evidence", False), LinkGraphFoundationFrontierRisk("risk-consensus-contradiction", "cross-method contradiction", "medium", "high", "keep contradictory methods visible and route for review", "consensus remains aggregate and method-limited", False), LinkGraphFoundationFrontierRisk("risk-source-change", "upstream receipt change", "low", "high", "address source version, checksum, and fixture content", "release must be replayed after source changes", False), LinkGraphFoundationFrontierRisk("risk-schema-break", "projection schema break", "low", "medium", "lock field names and validate export manifests", "downstream consumers must pin the schema address", False))
    return LinkGraphFoundationFrontierRiskRegister(risks, bool(risks) and not any(item.blocking for item in risks))


def risk_register_summary(register: LinkGraphFoundationFrontierRiskRegister) -> dict[str, Any]:
    return {"risk_count": len(register.risks), "blocking_count": len(register.blocking_risks), "high_impact_count": sum(item.impact == "high" for item in register.risks), "accepted": register.accepted}


__all__ = ["LinkGraphFoundationFrontierRisk", "LinkGraphFoundationFrontierRiskRegister", "build_link_graph_foundation_frontier_risk_register", "risk_register_summary"]
