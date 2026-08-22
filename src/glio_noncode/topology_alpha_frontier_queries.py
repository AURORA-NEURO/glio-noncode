"""Stable query helpers over sanitized alpha evaluation rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, TopologyAlphaFrontierEvaluationRow


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierQuery:
    query_id: str
    operation: str | None = None
    state: str | None = None
    role: str | None = None
    issue_code: str | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("query limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierQueryResult:
    query: TopologyAlphaFrontierQuery
    rows: tuple[TopologyAlphaFrontierEvaluationRow, ...]
    total_matches: int
    truncated: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.rows)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"query": self.query.to_dict(), "rows": [item.to_dict() for item in self.rows], "total_matches": self.total_matches, "truncated": self.truncated, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _matches(row: TopologyAlphaFrontierEvaluationRow, query: TopologyAlphaFrontierQuery) -> bool:
    return (query.operation is None or row.operation == query.operation) and (query.state is None or row.observed_state == query.state) and (query.role is None or row.role == query.role) and (query.issue_code is None or query.issue_code in row.observed_issue_codes)


def query_topology_alpha_frontier(evaluation: TopologyAlphaFrontierEvaluation, query: TopologyAlphaFrontierQuery) -> TopologyAlphaFrontierQueryResult:
    matches = tuple(row for row in evaluation.rows if _matches(row, query))
    rows = matches[: query.limit]
    return TopologyAlphaFrontierQueryResult(query, rows, len(matches), len(matches) > len(rows), all(item.adapter.content_address.startswith("sha256:") for item in rows))


def query_many_topology_alpha_frontier(evaluation: TopologyAlphaFrontierEvaluation, queries: Iterable[TopologyAlphaFrontierQuery]) -> tuple[TopologyAlphaFrontierQueryResult, ...]:
    return tuple(query_topology_alpha_frontier(evaluation, query) for query in queries)


__all__ = ["TopologyAlphaFrontierQuery", "TopologyAlphaFrontierQueryResult", "query_many_topology_alpha_frontier", "query_topology_alpha_frontier"]
