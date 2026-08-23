"""Consumer disposition matrix for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierDisposition, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationalCell:
    operation: str
    publish_count: int
    review_count: int
    quarantine_count: int
    action: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationalMatrix:
    cells: tuple[CohortAlphaFrontierOperationalCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_operational_matrix(policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierOperationalMatrix:
    cells = []
    for operation in ("C09", "C10", "C11", "C12"):
        rows = tuple(item for item in policy.decisions if item.operation == operation)
        publish = sum(item.disposition is CohortAlphaFrontierDisposition.PUBLISH for item in rows)
        review = sum(item.disposition is CohortAlphaFrontierDisposition.REVIEW for item in rows)
        quarantine = sum(item.disposition is CohortAlphaFrontierDisposition.QUARANTINE for item in rows)
        action = "publish bounded longitudinal summary" if publish else "hold for evidence review"
        body = {"operation": operation, "publish": publish, "review": review, "quarantine": quarantine, "action": action}
        cells.append(CohortAlphaFrontierOperationalCell(operation, publish, review, quarantine, action, len(rows) == 4, content_hash(body, prefix="alpha-operational-cell")))
    values = tuple(cells)
    return CohortAlphaFrontierOperationalMatrix(values, all(item.accepted for item in values), content_hash(values, prefix="alpha-operational"))


__all__ = ["CohortAlphaFrontierOperationalCell", "CohortAlphaFrontierOperationalMatrix", "build_cohort_alpha_frontier_operational_matrix"]
