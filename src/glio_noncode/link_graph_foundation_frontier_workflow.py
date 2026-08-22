"""Ordered workflow report for repeatable local and Actions verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_assertions import LinkGraphFoundationFrontierAssertionReport, evaluate_link_graph_foundation_frontier_assertions
from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation, evaluate_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, audit_link_graph_foundation_frontier_data, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_quality_dashboard import LinkGraphFoundationFrontierQualityDashboard, build_link_graph_foundation_frontier_quality_dashboard
from .link_graph_foundation_frontier_receipt_ledger import LinkGraphFoundationFrontierReceiptLedger, build_link_graph_foundation_frontier_receipt_ledger
from .link_graph_foundation_frontier_release_readiness import LinkGraphFoundationFrontierReleaseReadiness, build_link_graph_foundation_frontier_release_readiness
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierWorkflowStage:
    stage_id: str
    ordinal: int
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierWorkflowReport:
    fixture_id: str
    stages: tuple[LinkGraphFoundationFrontierWorkflowStage, ...]
    audit: Any
    evaluation: LinkGraphFoundationFrontierEvaluation
    receipts: LinkGraphFoundationFrontierReceiptLedger
    assertions: LinkGraphFoundationFrontierAssertionReport
    dashboard: LinkGraphFoundationFrontierQualityDashboard
    readiness: LinkGraphFoundationFrontierReleaseReadiness
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


def run_link_graph_foundation_frontier_workflow(fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierWorkflowReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    audit = audit_link_graph_foundation_frontier_data(value)
    evaluation = evaluate_link_graph_foundation_frontier_fixture(value)
    receipts = build_link_graph_foundation_frontier_receipt_ledger(value)
    assertions = evaluate_link_graph_foundation_frontier_assertions(value, evaluation)
    dashboard = build_link_graph_foundation_frontier_quality_dashboard(value, evaluation)
    readiness = build_link_graph_foundation_frontier_release_readiness(value, evaluation)
    stages = (LinkGraphFoundationFrontierWorkflowStage("audit", 1, audit.accepted, "fixture shape", audit.content_address), LinkGraphFoundationFrontierWorkflowStage("replay", 2, evaluation.accepted, "deterministic replay", evaluation.content_address), LinkGraphFoundationFrontierWorkflowStage("receipts", 3, receipts.accepted, "source coverage", receipts.content_address), LinkGraphFoundationFrontierWorkflowStage("assertions", 4, assertions.accepted, "verification assertions", assertions.content_address), LinkGraphFoundationFrontierWorkflowStage("dashboard", 5, dashboard.accepted, "quality indicators", dashboard.content_address), LinkGraphFoundationFrontierWorkflowStage("readiness", 6, readiness.publishable, "release readiness", readiness.content_address))
    return LinkGraphFoundationFrontierWorkflowReport(value.fixture_id, stages, audit, evaluation, receipts, assertions, dashboard, readiness, all(item.passed for item in stages))


def workflow_summary(report: LinkGraphFoundationFrontierWorkflowReport) -> dict[str, Any]:
    return {"fixture_id": report.fixture_id, "stage_count": len(report.stages), "passed_count": sum(item.passed for item in report.stages), "failed_stages": report.failed_stages, "publishable": report.readiness.publishable, "accepted": report.accepted}


__all__ = ["LinkGraphFoundationFrontierWorkflowReport", "LinkGraphFoundationFrontierWorkflowStage", "run_link_graph_foundation_frontier_workflow", "workflow_summary"]
