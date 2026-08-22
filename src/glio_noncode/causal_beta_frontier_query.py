"""Typed read-only queries over C05-C08 frontier results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation, CausalBetaFrontierEvaluationRow
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierQuery:
    operation: str | None = None
    state: str | None = None
    role: str | None = None
    issue_code: str | None = None
    record_id: str | None = None
    accepted_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierQueryResult:
    query: CausalBetaFrontierQuery
    fixture_id: str
    record_ids: tuple[str, ...]
    rows: tuple[CausalBetaFrontierEvaluationRow, ...]
    total_matches: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def empty(self) -> bool:
        return not self.rows

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"query": self.query.to_dict(), "fixture_id": self.fixture_id, "record_ids": self.record_ids, "rows": [item.to_dict() for item in self.rows], "total_matches": self.total_matches, "empty": self.empty}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierQueryIndex:
    fixture_id: str
    record_ids: tuple[str, ...]
    operations: tuple[str, ...]
    states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "record_ids": self.record_ids, "operations": self.operations, "states": self.states, "issue_codes": self.issue_codes}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_query_index(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation) -> CausalBetaFrontierQueryIndex:
    return CausalBetaFrontierQueryIndex(fixture.fixture_id, tuple(item.record_id for item in evaluation.rows), tuple(sorted({item.operation for item in evaluation.rows})), tuple(sorted({item.observed_state for item in evaluation.rows})), tuple(sorted({issue for item in evaluation.rows for issue in item.observed_issue_codes})))


def query_causal_beta_frontier(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, query: CausalBetaFrontierQuery, review: CausalBetaFrontierReviewQueue | None = None) -> CausalBetaFrontierQueryResult:
    review_map = {item.record_id: item for item in review.items} if review else {}
    rows = []
    record_map = fixture.record_map()
    for row in evaluation.rows:
        record = record_map[row.record_id]
        if query.operation is not None and row.operation != query.operation:
            continue
        if query.state is not None and row.observed_state != query.state:
            continue
        if query.role is not None and row.role != query.role:
            continue
        if query.issue_code is not None and query.issue_code not in row.observed_issue_codes:
            continue
        if query.record_id is not None and row.record_id != query.record_id:
            continue
        if query.accepted_only and (not row.state_match or not row.issue_match or review_map.get(row.record_id, None) and review_map[row.record_id].blocking):
            continue
        rows.append(row)
    values = tuple(rows)
    return CausalBetaFrontierQueryResult(query, fixture.fixture_id, tuple(item.record_id for item in values), values, len(values))


__all__ = ["CausalBetaFrontierQuery", "CausalBetaFrontierQueryIndex", "CausalBetaFrontierQueryResult", "build_causal_beta_frontier_query_index", "query_causal_beta_frontier"]
