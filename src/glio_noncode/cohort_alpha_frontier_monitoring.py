"""Monitoring signals for drift in state, coverage, and publication split."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierMonitorSignal:
    signal_id: str
    metric: str
    observed: float
    lower_bound: float
    upper_bound: float
    status: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierMonitoringReport:
    signals: tuple[CohortAlphaFrontierMonitorSignal, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_monitoring(metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierMonitoringReport:
    raw = (("acceptance", metrics.acceptance_percent, 100.0, 100.0), ("supported-share", 100 * metrics.supported_rows / max(1, metrics.total_rows), 0.0, 100.0), ("review-share", 100 * policy.review_count / max(1, len(policy.decisions)), 0.0, 100.0), ("quarantine-share", 100 * policy.quarantine_count / max(1, len(policy.decisions)), 0.0, 100.0))
    signals = tuple(CohortAlphaFrontierMonitorSignal(signal_id, signal_id, observed, lower, upper, "ok" if lower <= observed <= upper else "drift", content_hash({"id": signal_id, "metric": signal_id, "observed": observed, "lower": lower, "upper": upper}, prefix="alpha-monitor")) for signal_id, observed, lower, upper in raw)
    return CohortAlphaFrontierMonitoringReport(signals, all(item.status == "ok" for item in signals), content_hash(signals, prefix="alpha-monitoring"))


__all__ = ["CohortAlphaFrontierMonitorSignal", "CohortAlphaFrontierMonitoringReport", "build_cohort_alpha_frontier_monitoring"]
