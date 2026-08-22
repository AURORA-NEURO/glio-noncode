"""Twelve-stage executable pipeline for Domain 10 C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_accessibility import LinkGraphBetaFrontierAccessibilityReport, evaluate_link_graph_beta_frontier_accessibility
from .link_graph_beta_frontier_artifacts import LinkGraphBetaFrontierArtifactInventory, build_link_graph_beta_frontier_artifacts
from .link_graph_beta_frontier_bundle import LinkGraphBetaFrontierBundle, build_link_graph_beta_frontier_bundle
from .link_graph_beta_frontier_checks import LinkGraphBetaFrontierInvariantReport, run_link_graph_beta_frontier_invariants
from .link_graph_beta_frontier_contracts import LinkGraphBetaFrontierContractReport, build_link_graph_beta_frontier_contracts
from .link_graph_beta_frontier_depth import LinkGraphBetaFrontierDepthReport, audit_link_graph_beta_frontier_depth
from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation, evaluate_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_integrity import LinkGraphBetaFrontierIntegrityReport, evaluate_link_graph_beta_frontier_integrity
from .link_graph_beta_frontier_lineage import LinkGraphBetaFrontierLineage, build_link_graph_beta_frontier_lineage
from .link_graph_beta_frontier_metrics import LinkGraphBetaFrontierMetrics, build_link_graph_beta_frontier_metrics
from .link_graph_beta_frontier_observability import LinkGraphBetaFrontierObservabilityReport, build_link_graph_beta_frontier_trace
from .link_graph_beta_frontier_policy import LinkGraphBetaFrontierPolicyReport, evaluate_link_graph_beta_frontier_policy
from .link_graph_beta_frontier_provenance import LinkGraphBetaFrontierProvenanceGraph, build_link_graph_beta_frontier_provenance
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierDataAudit, LinkGraphBetaFrontierFixture, audit_link_graph_beta_frontier_data, default_link_graph_beta_frontier_fixture
from .link_graph_beta_frontier_quality_gate import LinkGraphBetaFrontierQualityReport, build_link_graph_beta_frontier_quality
from .link_graph_beta_frontier_reconciliation import LinkGraphBetaFrontierReconciliation, reconcile_link_graph_beta_frontier
from .link_graph_beta_frontier_release import LinkGraphBetaFrontierReleaseManifest, build_link_graph_beta_frontier_release
from .link_graph_beta_frontier_replay import LinkGraphBetaFrontierReplayReport, replay_link_graph_beta_frontier
from .link_graph_beta_frontier_review_queue import LinkGraphBetaFrontierReviewQueue, build_link_graph_beta_frontier_review_queue
from .link_graph_beta_frontier_scenario_matrix import LinkGraphBetaFrontierScenarioMatrix, build_link_graph_beta_frontier_scenario_matrix
from .link_graph_beta_frontier_schema import LinkGraphBetaFrontierSchemaReport, validate_link_graph_beta_frontier_schema
from .link_graph_beta_frontier_source_registry import LinkGraphBetaFrontierSourceRegistry, build_link_graph_beta_frontier_source_registry
from .link_graph_beta_frontier_validation_matrix import LinkGraphBetaFrontierValidationReport, build_link_graph_beta_frontier_validation_matrix
from .link_graph_beta_frontier_views import LinkGraphBetaFrontierReviewView, build_link_graph_beta_frontier_view
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierPipelineReport:
    run_id: str
    fixture: LinkGraphBetaFrontierFixture
    data: LinkGraphBetaFrontierDataAudit
    contracts: LinkGraphBetaFrontierContractReport
    sources: LinkGraphBetaFrontierSourceRegistry
    evaluation: LinkGraphBetaFrontierEvaluation
    schema: LinkGraphBetaFrontierSchemaReport
    metrics: LinkGraphBetaFrontierMetrics
    lineage: LinkGraphBetaFrontierLineage
    provenance: LinkGraphBetaFrontierProvenanceGraph
    policy: LinkGraphBetaFrontierPolicyReport
    reconciliation: LinkGraphBetaFrontierReconciliation
    quality: LinkGraphBetaFrontierQualityReport
    depth: LinkGraphBetaFrontierDepthReport
    validation: LinkGraphBetaFrontierValidationReport
    scenarios: LinkGraphBetaFrontierScenarioMatrix
    accessibility: LinkGraphBetaFrontierAccessibilityReport
    review_queue: LinkGraphBetaFrontierReviewQueue
    view: LinkGraphBetaFrontierReviewView
    integrity: LinkGraphBetaFrontierIntegrityReport
    release: LinkGraphBetaFrontierReleaseManifest
    bundle: LinkGraphBetaFrontierBundle
    artifacts: LinkGraphBetaFrontierArtifactInventory
    replay: LinkGraphBetaFrontierReplayReport
    trace: LinkGraphBetaFrontierObservabilityReport
    invariants: LinkGraphBetaFrontierInvariantReport
    stages: tuple[LinkGraphBetaFrontierStage, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"run_id": self.run_id, "fixture": self.fixture.content_address, "stages": self.stages, "accepted": self.accepted}))

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages if item.status != "passed")

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "fixture": self.fixture.to_dict(False), "data": self.data.to_dict(), "contracts": self.contracts.to_dict(), "sources": self.sources.to_dict(), "evaluation": self.evaluation.to_dict(), "schema": self.schema.to_dict(), "metrics": self.metrics.to_dict(), "lineage": self.lineage.to_dict(), "provenance": self.provenance.to_dict(), "policy": self.policy.to_dict(), "reconciliation": self.reconciliation.to_dict(), "quality": self.quality.to_dict(), "depth": self.depth.to_dict(), "validation": self.validation.to_dict(), "scenarios": self.scenarios.to_dict(), "accessibility": self.accessibility.to_dict(), "review_queue": self.review_queue.to_dict(), "view": self.view.to_dict(), "integrity": self.integrity.to_dict(), "release": self.release.to_dict(), "bundle": self.bundle.to_dict(), "artifacts": self.artifacts.to_dict(), "replay": self.replay.to_dict(), "trace": self.trace.to_dict(), "invariants": self.invariants.to_dict(), "stages": [item.to_dict() for item in self.stages], "failed_stages": self.failed_stages, "accepted": self.accepted, "content_address": self.content_address}


def _stage(stage_id: str, passed: bool, inputs: int, outputs: int, detail: str) -> LinkGraphBetaFrontierStage:
    return LinkGraphBetaFrontierStage(stage_id, "passed" if passed else "failed", inputs, outputs, detail)


def run_link_graph_beta_frontier_pipeline(fixture: LinkGraphBetaFrontierFixture | None = None, *, run_id: str = "link-graph-beta-frontier-run") -> LinkGraphBetaFrontierPipelineReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    data = audit_link_graph_beta_frontier_data(value)
    contracts = build_link_graph_beta_frontier_contracts()
    sources = build_link_graph_beta_frontier_source_registry(value)
    evaluation = evaluate_link_graph_beta_frontier_fixture(value)
    schema = validate_link_graph_beta_frontier_schema(value, evaluation)
    metrics = build_link_graph_beta_frontier_metrics(evaluation, value)
    lineage = build_link_graph_beta_frontier_lineage(value, evaluation)
    provenance = build_link_graph_beta_frontier_provenance(value, evaluation)
    policy = evaluate_link_graph_beta_frontier_policy(evaluation)
    reconciliation = reconcile_link_graph_beta_frontier(evaluation)
    quality = build_link_graph_beta_frontier_quality(value, data, schema, evaluation, reconciliation)
    depth = audit_link_graph_beta_frontier_depth(value, evaluation)
    validation = build_link_graph_beta_frontier_validation_matrix(evaluation)
    scenarios = build_link_graph_beta_frontier_scenario_matrix(evaluation)
    accessibility = evaluate_link_graph_beta_frontier_accessibility(value, evaluation)
    review_queue = build_link_graph_beta_frontier_review_queue(evaluation, policy)
    view = build_link_graph_beta_frontier_view(value, evaluation, review_queue)
    integrity = evaluate_link_graph_beta_frontier_integrity(value, evaluation)
    release = build_link_graph_beta_frontier_release(value, evaluation, quality)
    bundle = build_link_graph_beta_frontier_bundle(value, release, metrics, lineage)
    artifacts = build_link_graph_beta_frontier_artifacts(bundle, evaluation)
    replay = replay_link_graph_beta_frontier(evaluation)
    trace = build_link_graph_beta_frontier_trace(evaluation, run_id)
    invariants = run_link_graph_beta_frontier_invariants(value, evaluation)
    stages = (_stage("data_audit", data.accepted, len(value.records), 1, "fixture boundary"), _stage("contracts", contracts.accepted, 4, len(contracts.contracts), "operation contracts"), _stage("sources", sources.accepted, len(value.sources), len(sources.sources), "source receipts"), _stage("evaluation", evaluation.accepted, len(value.records), len(evaluation.rows), "typed replay"), _stage("schema", schema.accepted, len(schema.fields), len(schema.checks), "schema checks"), _stage("metrics", metrics.accepted, len(evaluation.rows), len(metrics.operations), "operation metrics"), _stage("lineage", lineage.accepted, len(value.records), len(lineage.edges), "lineage edges"), _stage("quality", quality.accepted, len(quality.checks), sum(item.passed for item in quality.checks), "quality gate"), _stage("validation", validation.accepted, len(evaluation.rows), len(validation.cells), "validation matrix"), _stage("review", review_queue.accepted and view.accepted, len(evaluation.rows), len(review_queue.entries), "review view"), _stage("release", release.publishable, len(value.records), 1, "release manifest"), _stage("artifacts", artifacts.accepted and replay.accepted and trace.accepted and invariants.accepted, len(value.records), len(artifacts.artifacts), "release artifacts"))
    accepted = all(item.status == "passed" for item in stages)
    return LinkGraphBetaFrontierPipelineReport(run_id, value, data, contracts, sources, evaluation, schema, metrics, lineage, provenance, policy, reconciliation, quality, depth, validation, scenarios, accessibility, review_queue, view, integrity, release, bundle, artifacts, replay, trace, invariants, stages, accepted)


__all__ = ["LinkGraphBetaFrontierPipelineReport", "LinkGraphBetaFrontierStage", "run_link_graph_beta_frontier_pipeline"]
