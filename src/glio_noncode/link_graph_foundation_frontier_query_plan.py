"""Repeatable query plans for baseline review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierQueryPlan:
    plan_id: str
    purpose: str
    filters: tuple[tuple[str, str], ...]
    projection: tuple[str, ...]
    expected_count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierQueryPlanCatalog:
    plans: tuple[LinkGraphFoundationFrontierQueryPlan, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def plan(self, plan_id: str) -> LinkGraphFoundationFrontierQueryPlan:
        for item in self.plans:
            if item.plan_id == plan_id:
                return item
        raise KeyError(plan_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"plans": [item.to_dict() for item in self.plans], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_query_plans() -> LinkGraphFoundationFrontierQueryPlanCatalog:
    plans = (LinkGraphFoundationFrontierQueryPlan("controls", "all control rows", (("role", "control"),), ("record_id", "operation", "expected_state", "expected_issue_codes"), 12), LinkGraphFoundationFrontierQueryPlan("foreign", "context boundary rows", (("record_id", "endswith:C3"),), ("record_id", "operation", "context_key", "observed_state"), 4), LinkGraphFoundationFrontierQueryPlan("ambiguity", "ambiguous candidates", (("state", "ambiguous"),), ("record_id", "operation", "issue_codes"), 3))
    return LinkGraphFoundationFrontierQueryPlanCatalog(plans, len(plans) == 3)


__all__ = ["LinkGraphFoundationFrontierQueryPlan", "LinkGraphFoundationFrontierQueryPlanCatalog", "build_link_graph_foundation_frontier_query_plans"]
