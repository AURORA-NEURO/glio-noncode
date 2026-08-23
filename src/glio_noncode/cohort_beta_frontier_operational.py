"""Consumer disposition matrix for publication, review, and quarantine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_policy import CohortBetaFrontierDisposition, CohortBetaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierOperationalCell:
    operation: str
    publish_count: int
    review_count: int
    quarantine_count: int
    consumer_action: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierOperationalMatrix:
    cells: tuple[CohortBetaFrontierOperationalCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_operational_matrix(policy: CohortBetaFrontierPolicy) -> CohortBetaFrontierOperationalMatrix:
    cells = []
    for operation in ("C05", "C06", "C07", "C08"):
        rows = tuple(item for item in policy.decisions if item.operation == operation)
        publish = sum(item.disposition is CohortBetaFrontierDisposition.PUBLISH for item in rows)
        review = sum(item.disposition is CohortBetaFrontierDisposition.REVIEW for item in rows)
        quarantine = sum(item.disposition is CohortBetaFrontierDisposition.QUARANTINE for item in rows)
        action = "publish bounded summary" if publish else "hold for evidence review"
        body = {"operation": operation, "publish": publish, "review": review, "quarantine": quarantine, "action": action}
        cells.append(CohortBetaFrontierOperationalCell(operation, publish, review, quarantine, action, len(rows) == 4, content_hash(body, prefix="operational-cell")))
    values = tuple(cells)
    return CohortBetaFrontierOperationalMatrix(values, all(item.accepted for item in values), content_hash(values, prefix="operational"))


__all__ = ["CohortBetaFrontierOperationalCell", "CohortBetaFrontierOperationalMatrix", "build_cohort_beta_frontier_operational_matrix"]
