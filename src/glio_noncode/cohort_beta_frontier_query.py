"""Deterministic review query over the release-safe view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_views import CohortBetaFrontierReviewRow, CohortBetaFrontierReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierQueryResult:
    operation: str | None
    rows: tuple[CohortBetaFrontierReviewRow, ...]
    total: int
    limit: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def query_cohort_beta_frontier(view: CohortBetaFrontierReviewView, *, operation: str | None = None, limit: int = 20) -> CohortBetaFrontierQueryResult:
    if limit < 1:
        raise ValueError("query limit must be positive")
    filtered = tuple(row for row in view.rows if operation is None or row.operation == operation)
    values = filtered[:limit]
    return CohortBetaFrontierQueryResult(operation, values, len(filtered), limit, content_hash({"operation": operation, "rows": values, "total": len(filtered)}, prefix="query"))


__all__ = ["CohortBetaFrontierQueryResult", "query_cohort_beta_frontier"]
