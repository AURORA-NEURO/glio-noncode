"""Typed query and filtering surfaces for causal foundation review rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation, CausalFoundationFrontierEvaluationRow
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierQuery:
    operation: str | None = None
    role: str | None = None
    state: str | None = None
    issue_code: str | None = None
    context_key: str | None = None
    record_prefix: str | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValueError("query limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierQueryResult:
    query: CausalFoundationFrontierQuery
    record_ids: tuple[str, ...]
    rows: tuple[CausalFoundationFrontierEvaluationRow, ...]
    total_matches: int
    truncated: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def accepted(self) -> bool:
        return self.total_matches == len(self.rows) or self.truncated

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"query": self.query.to_dict(), "record_ids": self.record_ids, "rows": [item.to_dict() for item in self.rows], "total_matches": self.total_matches, "truncated": self.truncated, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _matches(record: Any, row: CausalFoundationFrontierEvaluationRow, query: CausalFoundationFrontierQuery) -> bool:
    if query.operation is not None and row.operation != query.operation:
        return False
    if query.role is not None and row.role != query.role:
        return False
    if query.state is not None and row.observed_state != query.state:
        return False
    if query.issue_code is not None and query.issue_code not in row.observed_issue_codes:
        return False
    if query.context_key is not None and record.context_key != query.context_key:
        return False
    if query.record_prefix is not None and not row.record_id.startswith(query.record_prefix):
        return False
    return True


def query_causal_foundation_frontier(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, query: CausalFoundationFrontierQuery | None = None) -> CausalFoundationFrontierQueryResult:
    active = query or CausalFoundationFrontierQuery()
    records = fixture.record_map()
    selected = tuple(row for row in evaluation.rows if row.record_id in records and _matches(records[row.record_id], row, active))
    total = len(selected)
    rows = selected[: active.limit] if active.limit is not None else selected
    return CausalFoundationFrontierQueryResult(active, tuple(item.record_id for item in rows), rows, total, len(rows) < total)


def query_many_causal_foundation_frontier(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, queries: tuple[CausalFoundationFrontierQuery, ...]) -> tuple[CausalFoundationFrontierQueryResult, ...]:
    return tuple(query_causal_foundation_frontier(fixture, evaluation, query) for query in queries)


__all__ = ["CausalFoundationFrontierQuery", "CausalFoundationFrontierQueryResult", "query_causal_foundation_frontier", "query_many_causal_foundation_frontier"]
