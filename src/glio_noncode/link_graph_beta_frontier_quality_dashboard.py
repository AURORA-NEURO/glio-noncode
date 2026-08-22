"""Compact dashboard over independent beta frontier quality reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_benchmark import LinkGraphBetaFrontierBenchmarkReport, build_link_graph_beta_frontier_benchmark
from .link_graph_beta_frontier_conformance import LinkGraphBetaFrontierConformanceReport, evaluate_link_graph_beta_frontier_conformance
from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation, evaluate_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_invariant_catalog import LinkGraphBetaFrontierInvariantCatalogReport, evaluate_link_graph_beta_frontier_invariant_catalog
from .link_graph_beta_frontier_performance import LinkGraphBetaFrontierPerformanceReport, evaluate_link_graph_beta_frontier_performance
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDashboardIndicator:
    indicator_id: str
    label: str
    value: Any
    accepted: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierQualityDashboard:
    fixture_id: str
    indicators: tuple[LinkGraphBetaFrontierDashboardIndicator, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_indicators(self) -> tuple[str, ...]:
        return tuple(item.indicator_id for item in self.indicators if not item.accepted)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "indicators": [item.to_dict() for item in self.indicators], "failed_indicators": self.failed_indicators, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_quality_dashboard(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None, *, benchmark: LinkGraphBetaFrontierBenchmarkReport | None = None, conformance: LinkGraphBetaFrontierConformanceReport | None = None, invariants: LinkGraphBetaFrontierInvariantCatalogReport | None = None, performance: LinkGraphBetaFrontierPerformanceReport | None = None) -> LinkGraphBetaFrontierQualityDashboard:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or evaluate_link_graph_beta_frontier_fixture(value)
    reports = (replay, benchmark or build_link_graph_beta_frontier_benchmark(replay, value), conformance or evaluate_link_graph_beta_frontier_conformance(value, replay), invariants or evaluate_link_graph_beta_frontier_invariant_catalog(value, replay), performance or evaluate_link_graph_beta_frontier_performance(value, replay))
    indicators = tuple(LinkGraphBetaFrontierDashboardIndicator(f"indicator-{index + 1}", type(report).__name__, getattr(report, "accepted", False), getattr(report, "accepted", False), type(report).__name__) for index, report in enumerate(reports))
    return LinkGraphBetaFrontierQualityDashboard(value.fixture_id, indicators, all(item.accepted for item in indicators))


def quality_dashboard_summary(dashboard: LinkGraphBetaFrontierQualityDashboard) -> dict[str, Any]:
    return {"fixture_id": dashboard.fixture_id, "indicator_count": len(dashboard.indicators), "passed_count": sum(item.accepted for item in dashboard.indicators), "failed_count": len(dashboard.failed_indicators), "accepted": dashboard.accepted}


__all__ = ["LinkGraphBetaFrontierDashboardIndicator", "LinkGraphBetaFrontierQualityDashboard", "build_link_graph_beta_frontier_quality_dashboard", "quality_dashboard_summary"]
