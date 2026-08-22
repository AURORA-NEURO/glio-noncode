"""Compact quality dashboard assembled from the independent depth reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_benchmark import LinkGraphFoundationFrontierBenchmarkReport, build_link_graph_foundation_frontier_benchmark
from .link_graph_foundation_frontier_conformance import LinkGraphFoundationFrontierConformanceReport, evaluate_link_graph_foundation_frontier_conformance
from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation, evaluate_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_invariant_catalog import LinkGraphFoundationFrontierInvariantReport, evaluate_link_graph_foundation_frontier_invariants
from .link_graph_foundation_frontier_performance import LinkGraphFoundationFrontierPerformanceReport, evaluate_link_graph_foundation_frontier_performance
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierDashboardIndicator:
    indicator_id: str
    label: str
    value: Any
    accepted: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierQualityDashboard:
    fixture_id: str
    indicators: tuple[LinkGraphFoundationFrontierDashboardIndicator, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_indicators(self) -> tuple[str, ...]:
        return tuple(item.indicator_id for item in self.indicators if not item.accepted)

    def indicator(self, indicator_id: str) -> LinkGraphFoundationFrontierDashboardIndicator:
        return next(item for item in self.indicators if item.indicator_id == indicator_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "indicators": [item.to_dict() for item in self.indicators], "failed_indicators": self.failed_indicators, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_quality_dashboard(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None, *, benchmark: LinkGraphFoundationFrontierBenchmarkReport | None = None, conformance: LinkGraphFoundationFrontierConformanceReport | None = None, invariants: LinkGraphFoundationFrontierInvariantReport | None = None, performance: LinkGraphFoundationFrontierPerformanceReport | None = None) -> LinkGraphFoundationFrontierQualityDashboard:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or evaluate_link_graph_foundation_frontier_fixture(value)
    bench = benchmark or build_link_graph_foundation_frontier_benchmark(replay, value)
    conf = conformance or evaluate_link_graph_foundation_frontier_conformance(value, replay)
    inv = invariants or evaluate_link_graph_foundation_frontier_invariants(value, replay)
    perf = performance or evaluate_link_graph_foundation_frontier_performance(value, replay)
    indicators = (LinkGraphFoundationFrontierDashboardIndicator("replay", "fixture replay", replay.accepted, replay.accepted, f"{replay.state_match_count}/{len(replay.rows)} state rows"), LinkGraphFoundationFrontierDashboardIndicator("benchmark", "operation benchmark", bench.accepted, bench.accepted, f"{len(bench.results)} operation cases"), LinkGraphFoundationFrontierDashboardIndicator("conformance", "boundary conformance", conf.accepted, conf.accepted, f"{len(conf.results)} rules"), LinkGraphFoundationFrontierDashboardIndicator("invariants", "named invariants", inv.accepted, inv.accepted, f"{len(inv.results)} checks"), LinkGraphFoundationFrontierDashboardIndicator("performance", "resource budgets", perf.accepted, perf.accepted, f"{sum(item.work_units for item in perf.observations)} work units"))
    return LinkGraphFoundationFrontierQualityDashboard(value.fixture_id, indicators, all(item.accepted for item in indicators))


def quality_dashboard_summary(dashboard: LinkGraphFoundationFrontierQualityDashboard) -> dict[str, Any]:
    return {"fixture_id": dashboard.fixture_id, "indicator_count": len(dashboard.indicators), "passed_count": sum(item.accepted for item in dashboard.indicators), "failed_count": len(dashboard.failed_indicators), "accepted": dashboard.accepted}


__all__ = ["LinkGraphFoundationFrontierDashboardIndicator", "LinkGraphFoundationFrontierQualityDashboard", "build_link_graph_foundation_frontier_quality_dashboard", "quality_dashboard_summary"]
