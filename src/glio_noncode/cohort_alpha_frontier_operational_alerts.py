"""Operational alerts when a state mix or gate deviates from the fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationalAlert:
    alert_id: str
    severity: str
    metric: str
    observed: int
    expected: int
    active: bool
    response: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationalAlertReport:
    alerts: tuple[CohortAlphaFrontierOperationalAlert, ...]
    active_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_operational_alerts(metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierOperationalAlertReport:
    raw = (("row-count", "info", "rows", metrics.total_rows, 16, "rebuild fixture if cardinality changes"), ("supported-count", "warning", "supported", metrics.supported_rows, 4, "review source coverage if support changes"), ("review-count", "warning", "review", policy.review_count, 4, "open review queue"), ("quarantine-count", "warning", "quarantine", policy.quarantine_count, 8, "inspect context and abstention boundaries"), ("mismatch-count", "blocking", "mismatch", metrics.mismatch_rows, 0, "block package"))
    alerts = tuple(CohortAlphaFrontierOperationalAlert(alert_id, severity, metric, observed, expected, observed != expected, response, content_hash({"id": alert_id, "severity": severity, "metric": metric, "observed": observed, "expected": expected, "active": observed != expected}, prefix="alpha-alert")) for alert_id, severity, metric, observed, expected, response in raw)
    return CohortAlphaFrontierOperationalAlertReport(alerts, sum(item.active for item in alerts), all(item.severity and item.response for item in alerts), content_hash(alerts, prefix="alpha-alert-report"))


__all__ = ["CohortAlphaFrontierOperationalAlert", "CohortAlphaFrontierOperationalAlertReport", "evaluate_cohort_alpha_frontier_operational_alerts"]
