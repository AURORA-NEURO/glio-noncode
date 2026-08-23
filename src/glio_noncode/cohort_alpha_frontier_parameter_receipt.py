"""Parameter receipt with explicit defaults for each primitive."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_calibration import CohortAlphaFrontierCalibrationReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierParameterReceipt:
    operation: str
    parameters: dict[str, float]
    bounded: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierParameterReceiptSet:
    receipts: tuple[CohortAlphaFrontierParameterReceipt, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_parameter_receipts(calibration: CohortAlphaFrontierCalibrationReport) -> CohortAlphaFrontierParameterReceiptSet:
    grouped: dict[str, dict[str, float]] = {}
    for row in calibration.rows:
        grouped.setdefault(row.operation, {})[row.parameter] = row.nominal
    receipts = tuple(CohortAlphaFrontierParameterReceipt(operation, values, all(0.0 <= value <= 1.0 for value in values.values()), content_hash({"operation": operation, "parameters": values}, prefix="alpha-parameter-receipt")) for operation, values in sorted(grouped.items()))
    return CohortAlphaFrontierParameterReceiptSet(receipts, calibration.accepted and len(receipts) == 4 and all(item.bounded for item in receipts), content_hash(receipts, prefix="alpha-parameter-receipts"))


__all__ = ["CohortAlphaFrontierParameterReceipt", "CohortAlphaFrontierParameterReceiptSet", "build_cohort_alpha_frontier_parameter_receipts"]
