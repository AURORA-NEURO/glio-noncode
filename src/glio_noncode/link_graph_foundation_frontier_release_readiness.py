"""Release readiness roll-up over independent foundation reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_benchmark import LinkGraphFoundationFrontierBenchmarkReport, build_link_graph_foundation_frontier_benchmark
from .link_graph_foundation_frontier_conformance import LinkGraphFoundationFrontierConformanceReport, evaluate_link_graph_foundation_frontier_conformance
from .link_graph_foundation_frontier_export_manifest import LinkGraphFoundationFrontierExportManifest, build_link_graph_foundation_frontier_export_manifest
from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation, evaluate_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_invariant_catalog import LinkGraphFoundationFrontierInvariantReport, evaluate_link_graph_foundation_frontier_invariants
from .link_graph_foundation_frontier_performance import LinkGraphFoundationFrontierPerformanceReport, evaluate_link_graph_foundation_frontier_performance
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_risk_register import LinkGraphFoundationFrontierRiskRegister, build_link_graph_foundation_frontier_risk_register
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReadinessCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReleaseReadiness:
    fixture_id: str
    checks: tuple[LinkGraphFoundationFrontierReadinessCheck, ...]
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


def build_link_graph_foundation_frontier_release_readiness(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None, *, benchmark: LinkGraphFoundationFrontierBenchmarkReport | None = None, conformance: LinkGraphFoundationFrontierConformanceReport | None = None, invariants: LinkGraphFoundationFrontierInvariantReport | None = None, performance: LinkGraphFoundationFrontierPerformanceReport | None = None, manifest: LinkGraphFoundationFrontierExportManifest | None = None, risks: LinkGraphFoundationFrontierRiskRegister | None = None) -> LinkGraphFoundationFrontierReleaseReadiness:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or evaluate_link_graph_foundation_frontier_fixture(value)
    checks = (replay, benchmark or build_link_graph_foundation_frontier_benchmark(replay, value), conformance or evaluate_link_graph_foundation_frontier_conformance(value, replay), invariants or evaluate_link_graph_foundation_frontier_invariants(value, replay), performance or evaluate_link_graph_foundation_frontier_performance(value, replay), manifest or build_link_graph_foundation_frontier_export_manifest(value, replay), risks or build_link_graph_foundation_frontier_risk_register())
    rows = tuple(LinkGraphFoundationFrontierReadinessCheck(f"readiness-{index + 1}", bool(getattr(item, "accepted", getattr(item, "publishable", False))), type(item).__name__, getattr(item, "content_address", "")) for index, item in enumerate(checks))
    return LinkGraphFoundationFrontierReleaseReadiness(value.fixture_id, rows, all(item.passed for item in rows))


def release_readiness_summary(report: LinkGraphFoundationFrontierReleaseReadiness) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "check_count": len(report.checks), "passed_count": sum(item.passed for item in report.checks), "failed_count": len(report.failed_checks), "publishable": report.publishable}


__all__ = ["LinkGraphFoundationFrontierReadinessCheck", "LinkGraphFoundationFrontierReleaseReadiness", "build_link_graph_foundation_frontier_release_readiness", "release_readiness_summary"]
