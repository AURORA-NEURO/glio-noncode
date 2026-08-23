"""Stable row-order receipt for operation-major fixture serialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRowOrder:
    record_ids: tuple[str, ...]
    operation_offsets: dict[str, tuple[int, int]]
    sorted_by_operation: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def verify_cohort_alpha_frontier_row_order(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierRowOrder:
    ids = tuple(row.record_id for row in evaluation.rows)
    offsets = {operation: (next((index for index, row in enumerate(evaluation.rows) if row.operation == operation), -1), sum(row.operation == operation for row in evaluation.rows)) for operation in ("C09", "C10", "C11", "C12")}
    sorted_by_operation = tuple(row.operation for row in evaluation.rows) == tuple(operation for operation in ("C09", "C10", "C11", "C12") for _ in range(4))
    return CohortAlphaFrontierRowOrder(ids, offsets, sorted_by_operation, len(ids) == 16 and len(set(ids)) == 16 and sorted_by_operation, content_hash({"ids": ids, "offsets": offsets, "sorted": sorted_by_operation}, prefix="alpha-row-order"))


__all__ = ["CohortAlphaFrontierRowOrder", "verify_cohort_alpha_frontier_row_order"]
