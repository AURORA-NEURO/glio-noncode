"""Declared thresholds and boundary probes for the four testers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierThreshold:
    operation: str
    name: str
    default: float
    lower_bound: float
    upper_bound: float | None
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierThresholdReport:
    thresholds: tuple[CohortBetaFrontierThreshold, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_threshold_report() -> CohortBetaFrontierThresholdReport:
    raw = (("C05", "minimum_recurrent_samples", 2, 2, None, "recurrence needs distinct samples"), ("C05", "hotspot_window_bp", 50, 0, None, "local cluster radius is descriptive"), ("C06", "background_rate", 0.001, 0, None, "callable-space comparator is non-negative"), ("C07", "support", 0.5, 0, 1, "support is bounded"), ("C07", "ambiguity_margin", 0.05, 0, None, "ties remain visible"), ("C08", "minimum_genes", 2, 1, None, "set convergence needs gene coverage"))
    values = tuple(CohortBetaFrontierThreshold(operation, name, default, lower, upper, rationale, content_hash({"operation": operation, "name": name, "default": default}, prefix="threshold")) for operation, name, default, lower, upper, rationale in raw)
    return CohortBetaFrontierThresholdReport(values, all(item.default >= item.lower_bound and (item.upper_bound is None or item.default <= item.upper_bound) for item in values), content_hash(values, prefix="threshold-report"))


__all__ = ["CohortBetaFrontierThreshold", "CohortBetaFrontierThresholdReport", "build_cohort_beta_frontier_threshold_report"]
