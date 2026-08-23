"""Deterministic query index over the foundation review projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_views import CohortFoundationReviewView, CohortFoundationReviewViewRow


@dataclass(frozen=True, slots=True)
class CohortFoundationQueryResult:
    query_id: str
    rows: tuple[CohortFoundationReviewViewRow, ...]
    total: int
    facets: dict[str, tuple[str, ...]]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_cohort_foundation_frontier(view: CohortFoundationReviewView, *, query_id: str = "cohort-foundation-query", operation: str | None = None, state: str | None = None, disposition: str | None = None, limit: int | None = None) -> CohortFoundationQueryResult:
    rows = tuple(item for item in view.rows if (operation is None or item.operation == operation) and (state is None or item.actual_state == state) and (disposition is None or item.disposition == disposition))
    total = len(rows)
    if limit is not None:
        rows = rows[: max(0, limit)]
    facets = {"operation": tuple(sorted({item.operation for item in rows})), "state": tuple(sorted({item.actual_state for item in rows})), "disposition": tuple(sorted({item.disposition for item in rows}))}
    body = {"query_id": query_id, "rows": rows, "total": total, "facets": facets}
    return CohortFoundationQueryResult(query_id, rows, total, facets, content_hash(body))


__all__ = ["CohortFoundationQueryResult", "query_cohort_foundation_frontier"]
