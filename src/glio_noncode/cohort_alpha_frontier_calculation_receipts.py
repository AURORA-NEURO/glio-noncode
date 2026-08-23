"""Calculation receipts for aggregate counts and percentages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCalculationReceipt:
    calculation_id: str
    numerator: int
    denominator: int
    value: float
    formula: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCalculationReceiptSet:
    receipts: tuple[CohortAlphaFrontierCalculationReceipt, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_calculation_receipts(metrics: CohortAlphaFrontierMetrics) -> CohortAlphaFrontierCalculationReceiptSet:
    raw = (("acceptance", metrics.accepted_rows, metrics.total_rows), ("supported_share", metrics.supported_rows, metrics.total_rows), ("control_share", metrics.control_rows, metrics.total_rows), ("mismatch_share", metrics.mismatch_rows, metrics.total_rows))
    receipts = tuple(CohortAlphaFrontierCalculationReceipt(calculation_id, numerator, denominator, round(numerator / max(1, denominator), 6), f"{calculation_id} = numerator / denominator", content_hash({"id": calculation_id, "numerator": numerator, "denominator": denominator, "value": round(numerator / max(1, denominator), 6)}, prefix="alpha-calculation")) for calculation_id, numerator, denominator in raw)
    return CohortAlphaFrontierCalculationReceiptSet(receipts, len(receipts) == 4 and all(item.denominator == metrics.total_rows for item in receipts), content_hash(receipts, prefix="alpha-calculation-receipts"))


__all__ = ["CohortAlphaFrontierCalculationReceipt", "CohortAlphaFrontierCalculationReceiptSet", "build_cohort_alpha_frontier_calculation_receipts"]
