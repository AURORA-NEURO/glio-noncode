"""Small typed query language for review-safe C05-C08 navigation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .cohort_beta_frontier_views import CohortBetaFrontierReviewRow, CohortBetaFrontierReviewView
from .serialization import content_hash, jsonable


class CohortBetaFrontierQueryField(StrEnum):
    OPERATION = "operation"
    STATE = "state"
    DISPOSITION = "disposition"
    RECORD = "record_id"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierQueryClause:
    field: CohortBetaFrontierQueryField
    value: str
    negate: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierQueryPlan:
    clauses: tuple[CohortBetaFrontierQueryClause, ...]
    limit: int
    sort_field: CohortBetaFrontierQueryField
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierQueryExecution:
    plan: CohortBetaFrontierQueryPlan
    rows: tuple[CohortBetaFrontierReviewRow, ...]
    total_matches: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def parse_cohort_beta_frontier_query(text: str, *, limit: int = 20) -> CohortBetaFrontierQueryPlan:
    if limit < 1:
        raise ValueError("query limit must be positive")
    clauses = []
    for token in (part.strip() for part in text.split("and")):
        if not token:
            continue
        negate = token.startswith("!")
        normalized = token[1:] if negate else token
        if "=" not in normalized:
            raise ValueError("query clauses require field=value")
        field_text, value = (part.strip() for part in normalized.split("=", 1))
        field = CohortBetaFrontierQueryField(field_text)
        clauses.append(CohortBetaFrontierQueryClause(field, value, negate, content_hash({"field": field, "value": value, "negate": negate}, prefix="query-clause")))
    values = tuple(clauses)
    return CohortBetaFrontierQueryPlan(values, limit, CohortBetaFrontierQueryField.OPERATION, content_hash({"clauses": values, "limit": limit}, prefix="query-plan"))


def execute_cohort_beta_frontier_query(view: CohortBetaFrontierReviewView, plan: CohortBetaFrontierQueryPlan) -> CohortBetaFrontierQueryExecution:
    def matches(row: CohortBetaFrontierReviewRow, clause: CohortBetaFrontierQueryClause) -> bool:
        observed = str(getattr(row, clause.field.value))
        result = observed == clause.value
        return not result if clause.negate else result

    filtered = tuple(row for row in view.rows if all(matches(row, clause) for clause in plan.clauses))
    ordered = tuple(sorted(filtered, key=lambda row: (row.operation, row.record_id)))[: plan.limit]
    return CohortBetaFrontierQueryExecution(plan, ordered, len(filtered), True, content_hash({"plan": plan, "rows": ordered, "total": len(filtered)}, prefix="query-execution"))


def query_examples() -> Mapping[str, str]:
    return {"supported": "state=supported", "review": "disposition=review", "foreign": "state=out_of_domain", "operation": "operation=C08", "quarantined_except_foreign": "disposition=quarantine and !state=out_of_domain"}


__all__ = ["CohortBetaFrontierQueryClause", "CohortBetaFrontierQueryExecution", "CohortBetaFrontierQueryField", "CohortBetaFrontierQueryPlan", "execute_cohort_beta_frontier_query", "parse_cohort_beta_frontier_query", "query_examples"]
