"""Quality summary with category-level pass counts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierQualitySummaryRow:
    category: str
    passed: int
    total: int
    percent: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierQualitySummary:
    rows: tuple[CohortAlphaFrontierQualitySummaryRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def summarize_cohort_alpha_frontier_quality(gate: CohortAlphaFrontierQualityGate) -> CohortAlphaFrontierQualitySummary:
    rows = tuple(CohortAlphaFrontierQualitySummaryRow(item.check_id, 1 if item.accepted else 0, 1, 100.0 if item.accepted else 0.0, content_hash({"category": item.check_id, "passed": item.accepted}, prefix="alpha-quality-summary")) for item in gate.checks)
    return CohortAlphaFrontierQualitySummary(rows, gate.accepted and len(rows) == 6 and all(item.percent == 100.0 for item in rows), content_hash(rows, prefix="alpha-quality-summary-report"))


__all__ = ["CohortAlphaFrontierQualitySummary", "CohortAlphaFrontierQualitySummaryRow", "summarize_cohort_alpha_frontier_quality"]
