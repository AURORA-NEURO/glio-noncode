"""Calibration receipts for threshold values used by C09-C12 primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_thresholds import CohortAlphaFrontierThresholdReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCalibrationRow:
    operation: str
    parameter: str
    nominal: float
    lower: float
    upper: float
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCalibrationReport:
    rows: tuple[CohortAlphaFrontierCalibrationRow, ...]
    threshold_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_calibration(thresholds: CohortAlphaFrontierThresholdReport) -> CohortAlphaFrontierCalibrationReport:
    raw = (("C09", "clonal_threshold", 0.6, 0.0, 1.0, "fixture boundary calibration"), ("C09", "subclonal_threshold", 0.2, 0.0, 1.0, "fixture boundary calibration"), ("C10", "change_threshold", 0.25, 0.0, 1.0, "recurrence comparator calibration"), ("C11", "change_threshold", 0.2, 0.0, 1.0, "selection comparator calibration"), ("C12", "minimum_concordance", 0.75, 0.0, 1.0, "replication agreement calibration"))
    rows = tuple(CohortAlphaFrontierCalibrationRow(operation, parameter, nominal, lower, upper, rationale, content_hash({"operation": operation, "parameter": parameter, "nominal": nominal, "lower": lower, "upper": upper, "rationale": rationale}, prefix="alpha-calibration")) for operation, parameter, nominal, lower, upper, rationale in raw)
    return CohortAlphaFrontierCalibrationReport(rows, thresholds.content_address, thresholds.accepted and all(item.lower <= item.nominal <= item.upper for item in rows), content_hash({"rows": rows, "thresholds": thresholds.content_address}, prefix="alpha-calibration-report"))


__all__ = ["CohortAlphaFrontierCalibrationReport", "CohortAlphaFrontierCalibrationRow", "build_cohort_alpha_frontier_calibration"]
