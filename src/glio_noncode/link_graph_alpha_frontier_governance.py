"""Review governance rules for aggregate link evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierGovernanceRule:
    rule_id: str
    owner_scope: str
    required_artifact: str
    review_trigger: str
    decision: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierGovernanceReport:
    rules: tuple[LinkGraphAlphaFrontierGovernanceRule, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rules": [item.to_dict() for item in self.rules], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_governance_rules() -> tuple[LinkGraphAlphaFrontierGovernanceRule, ...]:
    return (
        LinkGraphAlphaFrontierGovernanceRule("source-receipt", "data stewardship", "source registry", "missing checksum or URI", "hold"),
        LinkGraphAlphaFrontierGovernanceRule("context-review", "scientific review", "context controls", "foreign context row", "abstain"),
        LinkGraphAlphaFrontierGovernanceRule("contradiction-review", "scientific review", "edge-level evidence", "contradictory state", "review"),
        LinkGraphAlphaFrontierGovernanceRule("release-review", "release review", "quality and replay reports", "any failed stage", "hold"),
    )


def build_link_graph_alpha_frontier_governance() -> LinkGraphAlphaFrontierGovernanceReport:
    rules = default_link_graph_alpha_frontier_governance_rules()
    checks = (check("rules_present", len(rules) == 4, "governance covers source, context, contradiction, and release"), check("decisions_present", all(item.decision for item in rules), "every trigger has a decision"), check("artifacts_present", all(item.required_artifact for item in rules), "every rule points to an artifact"))
    return LinkGraphAlphaFrontierGovernanceReport(rules, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierGovernanceReport", "LinkGraphAlphaFrontierGovernanceRule", "build_link_graph_alpha_frontier_governance", "default_link_graph_alpha_frontier_governance_rules"]
