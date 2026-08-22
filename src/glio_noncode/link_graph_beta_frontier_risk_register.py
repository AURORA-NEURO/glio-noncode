"""Risks, mitigations, and residual boundaries for beta links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierRisk:
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
        if self.likelihood == "high" or self.impact == "high":
            return "elevated"
        return "managed"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierRiskRegister:
    risks: tuple[LinkGraphBetaFrontierRisk, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_risks(self) -> tuple[str, ...]:
        return tuple(item.risk_id for item in self.risks if item.blocking)

    def by_rating(self, rating: str) -> tuple[LinkGraphBetaFrontierRisk, ...]:
        return tuple(item for item in self.risks if item.rating == rating)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"risks": [item.to_dict() for item in self.risks], "blocking_risks": self.blocking_risks, "rating_counts": {rating: len(self.by_rating(rating)) for rating in ("critical", "elevated", "managed")}, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_risk_register() -> LinkGraphBetaFrontierRiskRegister:
    risks = (LinkGraphBetaFrontierRisk("risk-activity-components", "component scale drift", "medium", "high", "retain activity and contact separately with declared scale", "aggregate components are not mechanism evidence", False), LinkGraphBetaFrontierRisk("risk-coaccess-context", "coaccessibility context drift", "medium", "high", "gate every path by exact context key", "transport requires external validation", False), LinkGraphBetaFrontierRisk("risk-qtl-transform", "p or q transform overinterpretation", "low", "high", "retain raw values and bounded support alongside effect size", "support is descriptive", False), LinkGraphBetaFrontierRisk("risk-allele-conflict", "direction conflict hidden", "medium", "high", "preserve gain and loss rows and contradiction state", "conflict remains a review outcome", False), LinkGraphBetaFrontierRisk("risk-receipt-change", "upstream receipt change", "low", "high", "address source versions, checksums, and fixture content", "release requires replay after change", False))
    return LinkGraphBetaFrontierRiskRegister(risks, bool(risks) and not any(item.blocking for item in risks))


def risk_register_summary(register: LinkGraphBetaFrontierRiskRegister) -> dict[str, Any]:
    return {"risk_count": len(register.risks), "blocking_count": len(register.blocking_risks), "high_impact_count": sum(item.impact == "high" for item in register.risks), "accepted": register.accepted}


__all__ = ["LinkGraphBetaFrontierRisk", "LinkGraphBetaFrontierRiskRegister", "build_link_graph_beta_frontier_risk_register", "risk_register_summary"]
