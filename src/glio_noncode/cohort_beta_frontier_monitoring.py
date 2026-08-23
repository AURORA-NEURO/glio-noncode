"""Post-release monitoring signals for source, state, and comparator drift."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_metrics import CohortBetaFrontierMetrics
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


class CohortBetaFrontierMonitorLevel(StrEnum):
    NOMINAL = "nominal"
    WATCH = "watch"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierMonitorRule:
    metric_id: str
    description: str
    nominal_min: float
    watch_min: float
    stop_min: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierMonitorSignal:
    metric_id: str
    observed: float
    level: CohortBetaFrontierMonitorLevel
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierMonitoringReport:
    rules: tuple[CohortBetaFrontierMonitorRule, ...]
    signals: tuple[CohortBetaFrontierMonitorSignal, ...]
    nominal_count: int
    watch_count: int
    stop_count: int
    accepted: bool
    content_address: str

    def signal(self, metric_id: str) -> CohortBetaFrontierMonitorSignal:
        return next(item for item in self.signals if item.metric_id == metric_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_monitor_rules() -> tuple[CohortBetaFrontierMonitorRule, ...]:
    raw = (("acceptance_percent", "accepted fixture rows remain complete", 100.0, 95.0, 80.0), ("operation_count", "all four operations remain represented", 4.0, 4.0, 3.0), ("supported_count", "positive supported paths remain represented", 4.0, 3.0, 1.0), ("source_count", "public source registry remains closed", 6.0, 5.0, 4.0), ("review_count", "review queue remains bounded", 12.0, 20.0, 32.0), ("context_isolation", "foreign paths remain quarantined", 4.0, 4.0, 2.0))
    return tuple(CohortBetaFrontierMonitorRule(metric_id, description, nominal, watch, stop, content_hash({"metric_id": metric_id, "nominal": nominal, "watch": watch, "stop": stop}, prefix="monitor-rule")) for metric_id, description, nominal, watch, stop in raw)


def _level(rule: CohortBetaFrontierMonitorRule, observed: float) -> CohortBetaFrontierMonitorLevel:
    if rule.metric_id == "review_count":
        if observed <= rule.nominal_min:
            return CohortBetaFrontierMonitorLevel.NOMINAL
        if observed <= rule.watch_min:
            return CohortBetaFrontierMonitorLevel.WATCH
        return CohortBetaFrontierMonitorLevel.STOP
    if observed >= rule.nominal_min:
        return CohortBetaFrontierMonitorLevel.NOMINAL
    if observed >= rule.watch_min:
        return CohortBetaFrontierMonitorLevel.WATCH
    return CohortBetaFrontierMonitorLevel.STOP


def build_cohort_beta_frontier_monitoring_report(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, metrics: CohortBetaFrontierMetrics, *, source_count: int, review_count: int, foreign_count: int, rules: Iterable[CohortBetaFrontierMonitorRule] | None = None) -> CohortBetaFrontierMonitoringReport:
    values = {"acceptance_percent": metrics.acceptance_percent, "operation_count": float(len(metrics.operations)), "supported_count": float(metrics.supported_rows), "source_count": float(source_count), "review_count": float(review_count), "context_isolation": float(foreign_count)}
    selected = tuple(rules or default_cohort_beta_frontier_monitor_rules())
    signals = []
    for rule in selected:
        observed = values[rule.metric_id]
        level = _level(rule, observed)
        detail = f"{rule.metric_id} observed={observed} level={level.value}"
        signals.append(CohortBetaFrontierMonitorSignal(rule.metric_id, observed, level, detail, content_hash({"metric_id": rule.metric_id, "observed": observed, "level": level}, prefix="monitor-signal")))
    values_tuple = tuple(signals)
    body = {"fixture": fixture.fixture_id, "evaluation": evaluation.content_address, "signals": values_tuple}
    return CohortBetaFrontierMonitoringReport(selected, values_tuple, sum(item.level is CohortBetaFrontierMonitorLevel.NOMINAL for item in values_tuple), sum(item.level is CohortBetaFrontierMonitorLevel.WATCH for item in values_tuple), sum(item.level is CohortBetaFrontierMonitorLevel.STOP for item in values_tuple), all(item.level is not CohortBetaFrontierMonitorLevel.STOP for item in values_tuple), content_hash(body, prefix="monitoring"))


def monitoring_summary(report: CohortBetaFrontierMonitoringReport) -> Mapping[str, Any]:
    return {"nominal_count": report.nominal_count, "watch_count": report.watch_count, "stop_count": report.stop_count, "accepted": report.accepted, "signals": {item.metric_id: item.level.value for item in report.signals}}


__all__ = ["CohortBetaFrontierMonitorLevel", "CohortBetaFrontierMonitorRule", "CohortBetaFrontierMonitorSignal", "CohortBetaFrontierMonitoringReport", "build_cohort_beta_frontier_monitoring_report", "default_cohort_beta_frontier_monitor_rules", "monitoring_summary"]
