"""Small deterministic query surface over evaluated alpha rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation, CohortAlphaFrontierEvaluationRow
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierQuery:
    operation: str | None = None
    state: str | None = None
    accepted: bool | None = None
    record_prefix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierQueryResult:
    query: CohortAlphaFrontierQuery
    rows: tuple[CohortAlphaFrontierEvaluationRow, ...]
    count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_cohort_alpha_frontier(evaluation: CohortAlphaFrontierEvaluation, query: CohortAlphaFrontierQuery) -> CohortAlphaFrontierQueryResult:
    rows = tuple(row for row in evaluation.rows if (query.operation is None or row.operation == query.operation) and (query.state is None or row.observed_state.value == query.state) and (query.accepted is None or row.accepted == query.accepted) and (query.record_prefix is None or row.record_id.startswith(query.record_prefix)))
    return CohortAlphaFrontierQueryResult(query, rows, len(rows), content_hash({"query": query, "rows": rows}, prefix="alpha-query"))


def default_cohort_alpha_frontier_queries() -> tuple[CohortAlphaFrontierQuery, ...]:
    return (CohortAlphaFrontierQuery(operation="C09"), CohortAlphaFrontierQuery(state="supported"), CohortAlphaFrontierQuery(accepted=True), CohortAlphaFrontierQuery(record_prefix="C12-"))


__all__ = ["CohortAlphaFrontierQuery", "CohortAlphaFrontierQueryResult", "default_cohort_alpha_frontier_queries", "query_cohort_alpha_frontier"]
