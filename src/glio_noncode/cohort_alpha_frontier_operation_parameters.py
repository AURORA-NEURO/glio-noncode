"""Declared operation parameter profiles and valid ranges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_calibration import CohortAlphaFrontierCalibrationReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierParameterProfile:
    operation: str
    parameter: str
    nominal: float
    minimum: float
    maximum: float
    unit: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierParameterReport:
    profiles: tuple[CohortAlphaFrontierParameterProfile, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_parameter_report(calibration: CohortAlphaFrontierCalibrationReport) -> CohortAlphaFrontierParameterReport:
    profiles = tuple(CohortAlphaFrontierParameterProfile(row.operation, row.parameter, row.nominal, row.lower, row.upper, "fraction", row.lower <= row.nominal <= row.upper, content_hash({"operation": row.operation, "parameter": row.parameter, "nominal": row.nominal, "minimum": row.lower, "maximum": row.upper}, prefix="alpha-parameter")) for row in calibration.rows)
    return CohortAlphaFrontierParameterReport(profiles, calibration.accepted and len(profiles) == 5 and all(item.accepted for item in profiles), content_hash(profiles, prefix="alpha-parameter-report"))


__all__ = ["CohortAlphaFrontierParameterProfile", "CohortAlphaFrontierParameterReport", "build_cohort_alpha_frontier_parameter_report"]
