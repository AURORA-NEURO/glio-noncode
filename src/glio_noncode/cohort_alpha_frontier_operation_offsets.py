"""Operation offset receipt used by JSONL and CSV serializers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationOffset:
    operation: str
    start: int
    end: int
    row_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationOffsets:
    offsets: tuple[CohortAlphaFrontierOperationOffset, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_operation_offsets(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierOperationOffsets:
    offsets = []
    for operation in ("C09", "C10", "C11", "C12"):
        positions = [index for index, row in enumerate(evaluation.rows) if row.operation == operation]
        start = min(positions) if positions else -1
        end = max(positions) + 1 if positions else -1
        offsets.append(CohortAlphaFrontierOperationOffset(operation, start, end, len(positions), content_hash({"operation": operation, "start": start, "end": end, "count": len(positions)}, prefix="alpha-offset")))
    values = tuple(offsets)
    return CohortAlphaFrontierOperationOffsets(values, len(values) == 4 and all(item.row_count == 4 and item.end - item.start == 4 for item in values), content_hash(values, prefix="alpha-offsets"))


__all__ = ["CohortAlphaFrontierOperationOffset", "CohortAlphaFrontierOperationOffsets", "build_cohort_alpha_frontier_operation_offsets"]
