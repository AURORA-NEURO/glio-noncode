"""Declared query plans for beta review and quality surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierQueryPlan:
    query_id: str
    purpose: str
    filters: tuple[str, ...]
    projection: tuple[str, ...]
    ordering: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierQueryPlanCatalog:
    plans: tuple[LinkGraphBetaFrontierQueryPlan, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def plan(self, query_id: str) -> LinkGraphBetaFrontierQueryPlan:
        return next(item for item in self.plans if item.query_id == query_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"plans": [item.to_dict() for item in self.plans], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_query_plans() -> LinkGraphBetaFrontierQueryPlanCatalog:
    plans = (LinkGraphBetaFrontierQueryPlan("review-controls", "find non-positive control outcomes", ("role=control",), ("record_id", "operation", "state", "issue_codes"), ("priority", "record_id"), "review is not a causal conclusion"), LinkGraphBetaFrontierQueryPlan("operation-balance", "summarize operation counts", (), ("operation", "record_count", "state_accuracy"), ("operation",), "aggregate counts do not measure transport"), LinkGraphBetaFrontierQueryPlan("context-boundary", "find foreign context rows", ("context_key!=target",), ("record_id", "operation", "context_key", "state"), ("record_id",), "foreign context remains gated"), LinkGraphBetaFrontierQueryPlan("direction-conflicts", "find allele direction contradictions", ("issue=direction_conflict",), ("record_id", "directions", "state"), ("record_id",), "direction conflict remains visible"))
    return LinkGraphBetaFrontierQueryPlanCatalog(plans, bool(plans) and all(item.filters is not None and item.projection and item.limitation for item in plans))


__all__ = ["LinkGraphBetaFrontierQueryPlan", "LinkGraphBetaFrontierQueryPlanCatalog", "build_link_graph_beta_frontier_query_plans"]
