"""Ordered verification workflow for beta frontier release checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_assertions import LinkGraphBetaFrontierAssertionReport, evaluate_link_graph_beta_frontier_assertions
from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation, evaluate_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, audit_link_graph_beta_frontier_data, default_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_quality_dashboard import LinkGraphBetaFrontierQualityDashboard, build_link_graph_beta_frontier_quality_dashboard
from .link_graph_beta_frontier_receipt_ledger import LinkGraphBetaFrontierReceiptLedger, build_link_graph_beta_frontier_receipt_ledger
from .link_graph_beta_frontier_release_readiness import LinkGraphBetaFrontierReleaseReadiness, build_link_graph_beta_frontier_release_readiness
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierWorkflowStage:
    stage_id: str
    ordinal: int
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierWorkflowReport:
    fixture_id: str
    stages: tuple[LinkGraphBetaFrontierWorkflowStage, ...]
    audit: Any
    evaluation: LinkGraphBetaFrontierEvaluation
    receipts: LinkGraphBetaFrontierReceiptLedger
    assertions: LinkGraphBetaFrontierAssertionReport
    dashboard: LinkGraphBetaFrontierQualityDashboard
    readiness: LinkGraphBetaFrontierReleaseReadiness
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "stages": [item.to_dict() for item in self.stages], "failed_stages": self.failed_stages, "audit": self.audit.to_dict(), "evaluation": self.evaluation.to_dict(), "receipts": self.receipts.to_dict(), "assertions": self.assertions.to_dict(), "dashboard": self.dashboard.to_dict(), "readiness": self.readiness.to_dict(), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_beta_frontier_workflow(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierWorkflowReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    audit = audit_link_graph_beta_frontier_data(value)
    evaluation = evaluate_link_graph_beta_frontier_fixture(value)
    receipts = build_link_graph_beta_frontier_receipt_ledger(value)
    assertions = evaluate_link_graph_beta_frontier_assertions(value, evaluation)
    dashboard = build_link_graph_beta_frontier_quality_dashboard(value, evaluation)
    readiness = build_link_graph_beta_frontier_release_readiness(value, evaluation)
    stages = (LinkGraphBetaFrontierWorkflowStage("audit", 1, audit.accepted, "fixture shape", audit.content_address), LinkGraphBetaFrontierWorkflowStage("replay", 2, evaluation.accepted, "deterministic replay", evaluation.content_address), LinkGraphBetaFrontierWorkflowStage("receipts", 3, receipts.accepted, "receipt ledger", receipts.content_address), LinkGraphBetaFrontierWorkflowStage("assertions", 4, assertions.accepted, "explicit checks", assertions.content_address), LinkGraphBetaFrontierWorkflowStage("dashboard", 5, dashboard.accepted, "quality indicators", dashboard.content_address), LinkGraphBetaFrontierWorkflowStage("readiness", 6, readiness.publishable, "release readiness", readiness.content_address))
    return LinkGraphBetaFrontierWorkflowReport(value.fixture_id, stages, audit, evaluation, receipts, assertions, dashboard, readiness, all(item.passed for item in stages))


def workflow_summary(report: LinkGraphBetaFrontierWorkflowReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "stage_count": len(report.stages), "passed_count": sum(item.passed for item in report.stages), "failed_stages": report.failed_stages, "publishable": report.readiness.publishable, "accepted": report.accepted}


__all__ = ["LinkGraphBetaFrontierWorkflowReport", "LinkGraphBetaFrontierWorkflowStage", "run_link_graph_beta_frontier_workflow", "workflow_summary"]
