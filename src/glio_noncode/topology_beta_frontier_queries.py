"""Read-only query helpers over beta evaluation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation, TopologyBetaFrontierEvaluationRow


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierQuery:
    operation: str | None = None
    state: str | None = None
    role: str | None = None
    source_id: str | None = None
    issue_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierQueryResult:
    query: TopologyBetaFrontierQuery
    rows: tuple[TopologyBetaFrontierEvaluationRow, ...]
    count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.rows)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"query": self.query.to_dict(), "record_ids": self.record_ids(), "count": self.count, "accepted": self.accepted, "rows": [item.to_dict() for item in self.rows]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def query_topology_beta_frontier(evaluation: TopologyBetaFrontierEvaluation, query: TopologyBetaFrontierQuery | None = None) -> TopologyBetaFrontierQueryResult:
    value = query or TopologyBetaFrontierQuery()
    rows = tuple(item for item in evaluation.rows if (value.operation is None or item.operation == value.operation) and (value.state is None or item.observed_state == value.state) and (value.role is None or item.role == value.role) and (value.source_id is None or value.source_id in item.adapter.source_ids) and (value.issue_code is None or value.issue_code in item.observed_issue_codes))
    return TopologyBetaFrontierQueryResult(value, rows, len(rows), evaluation.accepted)


def query_topology_beta_frontier_summary(evaluation: TopologyBetaFrontierEvaluation) -> dict[str, Any]:
    return {"record_count": len(evaluation.rows), "accepted": evaluation.accepted, "operations": {operation: query_topology_beta_frontier(evaluation, TopologyBetaFrontierQuery(operation=operation)).count for operation in sorted({item.operation for item in evaluation.rows})}, "states": {state: query_topology_beta_frontier(evaluation, TopologyBetaFrontierQuery(state=state)).count for state in sorted({item.observed_state for item in evaluation.rows})}, "controls": query_topology_beta_frontier(evaluation, TopologyBetaFrontierQuery(role="control")).count}


__all__ = ["TopologyBetaFrontierQuery", "TopologyBetaFrontierQueryResult", "query_topology_beta_frontier", "query_topology_beta_frontier_summary"]
