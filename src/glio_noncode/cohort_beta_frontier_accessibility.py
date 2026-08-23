"""Review projection accessibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_views import CohortBetaFrontierReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAccessibilityReport:
    required_columns: tuple[str, ...]
    present_columns: tuple[str, ...]
    row_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_accessibility_report(view: CohortBetaFrontierReviewView) -> CohortBetaFrontierAccessibilityReport:
    required = ("operation", "record_id", "state", "disposition", "reason")
    present = tuple(name for name in required if view.rows and all(hasattr(row, name) for row in view.rows))
    return CohortBetaFrontierAccessibilityReport(required, present, len(view.rows), set(required) == set(present) and bool(view.rows), content_hash({"required": required, "present": present, "row_count": len(view.rows)}, prefix="accessibility"))


__all__ = ["CohortBetaFrontierAccessibilityReport", "build_cohort_beta_frontier_accessibility_report"]
