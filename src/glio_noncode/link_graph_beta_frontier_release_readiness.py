"""Release readiness roll-up for the beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_benchmark import LinkGraphBetaFrontierBenchmarkReport, build_link_graph_beta_frontier_benchmark
from .link_graph_beta_frontier_conformance import LinkGraphBetaFrontierConformanceReport, evaluate_link_graph_beta_frontier_conformance
from .link_graph_beta_frontier_export_manifest import LinkGraphBetaFrontierExportManifest, build_link_graph_beta_frontier_export_manifest
from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation, evaluate_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_invariant_catalog import LinkGraphBetaFrontierInvariantCatalogReport, evaluate_link_graph_beta_frontier_invariant_catalog
from .link_graph_beta_frontier_performance import LinkGraphBetaFrontierPerformanceReport, evaluate_link_graph_beta_frontier_performance
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_risk_register import LinkGraphBetaFrontierRiskRegister, build_link_graph_beta_frontier_risk_register
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReadinessCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReleaseReadiness:
    fixture_id: str
    checks: tuple[LinkGraphBetaFrontierReadinessCheck, ...]
    publishable: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": [item.to_dict() for item in self.checks], "failed_checks": self.failed_checks, "publishable": self.publishable}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_release_readiness(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None, *, benchmark: LinkGraphBetaFrontierBenchmarkReport | None = None, conformance: LinkGraphBetaFrontierConformanceReport | None = None, invariants: LinkGraphBetaFrontierInvariantCatalogReport | None = None, performance: LinkGraphBetaFrontierPerformanceReport | None = None, manifest: LinkGraphBetaFrontierExportManifest | None = None, risks: LinkGraphBetaFrontierRiskRegister | None = None) -> LinkGraphBetaFrontierReleaseReadiness:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or evaluate_link_graph_beta_frontier_fixture(value)
    reports = (replay, benchmark or build_link_graph_beta_frontier_benchmark(replay, value), conformance or evaluate_link_graph_beta_frontier_conformance(value, replay), invariants or evaluate_link_graph_beta_frontier_invariant_catalog(value, replay), performance or evaluate_link_graph_beta_frontier_performance(value, replay), manifest or build_link_graph_beta_frontier_export_manifest(value, replay), risks or build_link_graph_beta_frontier_risk_register())
    checks = tuple(LinkGraphBetaFrontierReadinessCheck(f"readiness-{index + 1}", bool(getattr(report, "accepted", getattr(report, "publishable", False))), type(report).__name__, getattr(report, "content_address", "")) for index, report in enumerate(reports))
    return LinkGraphBetaFrontierReleaseReadiness(value.fixture_id, checks, bool(checks) and all(item.passed for item in checks))


def release_readiness_summary(report: LinkGraphBetaFrontierReleaseReadiness) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "check_count": len(report.checks), "passed_count": sum(item.passed for item in report.checks), "failed_count": len(report.failed_checks), "publishable": report.publishable}


__all__ = ["LinkGraphBetaFrontierReadinessCheck", "LinkGraphBetaFrontierReleaseReadiness", "build_link_graph_beta_frontier_release_readiness", "release_readiness_summary"]
