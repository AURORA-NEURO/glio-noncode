"""Validated query plans for repeatable alpha review slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, TopologyAlphaFrontierEvaluationRow


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierQueryPredicate:
    field: str
    operator: str
    value: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierQueryPlan:
    plan_id: str
    title: str
    predicates: tuple[TopologyAlphaFrontierQueryPredicate, ...]
    projection: tuple[str, ...]
    sort_fields: tuple[str, ...]
    limit: int
    purpose: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("query plan limit must be positive")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"plan_id": self.plan_id, "title": self.title, "predicates": [item.to_dict() for item in self.predicates], "projection": self.projection, "sort_fields": self.sort_fields, "limit": self.limit, "purpose": self.purpose, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierQueryPlanResult:
    plan_id: str
    rows: tuple[dict[str, Any], ...]
    matched_count: int
    truncated: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"plan_id": self.plan_id, "rows": self.rows, "matched_count": self.matched_count, "truncated": self.truncated, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_alpha_frontier_query_plans() -> tuple[TopologyAlphaFrontierQueryPlan, ...]:
    return (TopologyAlphaFrontierQueryPlan("all-controls", "All open controls", (TopologyAlphaFrontierQueryPredicate("role", "equals", "control", "retain all controls"),), ("record_id", "operation", "state", "issues", "result_address"), ("operation", "record_id"), 12, "review queue reproduction", True), TopologyAlphaFrontierQueryPlan("foreign-context", "Foreign context controls", (TopologyAlphaFrontierQueryPredicate("issue", "contains", "context_mismatch", "find context transport controls"),), ("record_id", "operation", "state", "issues"), ("operation", "record_id"), 4, "context boundary review", True), TopologyAlphaFrontierQueryPlan("positive-support", "Positive support paths", (TopologyAlphaFrontierQueryPredicate("state", "equals", "supported", "find supported aggregate rows"), TopologyAlphaFrontierQueryPredicate("role", "equals", "positive", "exclude controls")), ("record_id", "operation", "state", "result_address"), ("operation", "record_id"), 4, "release summary", True))


def _matches(row: TopologyAlphaFrontierEvaluationRow, predicate: TopologyAlphaFrontierQueryPredicate) -> bool:
    if predicate.field == "role":
        observed = row.role
    elif predicate.field == "state":
        observed = row.observed_state
    elif predicate.field == "issue":
        return predicate.value in row.observed_issue_codes
    else:
        return False
    return observed == predicate.value if predicate.operator == "equals" else predicate.value in observed


def execute_topology_alpha_frontier_query_plan(evaluation: TopologyAlphaFrontierEvaluation, plan: TopologyAlphaFrontierQueryPlan) -> TopologyAlphaFrontierQueryPlanResult:
    matches = tuple(row for row in evaluation.rows if all(_matches(row, predicate) for predicate in plan.predicates))
    ordered = tuple(sorted(matches, key=lambda row: tuple(row.operation if field == "operation" else row.record_id if field == "record_id" else row.observed_state for field in plan.sort_fields)))
    selected = ordered[: plan.limit]
    rows = tuple({"record_id": row.record_id, "operation": row.operation, "state": row.observed_state, "issues": row.observed_issue_codes, "result_address": row.adapter.content_address} for row in selected)
    return TopologyAlphaFrontierQueryPlanResult(plan.plan_id, rows, len(matches), len(matches) > len(selected), plan.accepted and all(row["result_address"].startswith("sha256:") for row in rows))


TopologyAlphaFrontierQueryPlanPredicate = TopologyAlphaFrontierQueryPredicate


__all__ = ["TopologyAlphaFrontierQueryPlan", "TopologyAlphaFrontierQueryPlanPredicate", "TopologyAlphaFrontierQueryPredicate", "TopologyAlphaFrontierQueryPlanResult", "default_topology_alpha_frontier_query_plans", "execute_topology_alpha_frontier_query_plan"]
