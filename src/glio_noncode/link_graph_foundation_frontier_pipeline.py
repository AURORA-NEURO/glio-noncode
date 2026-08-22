"""Twelve-stage executable pipeline for Domain 10 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_accessibility import LinkGraphFoundationFrontierAccessibilityReport, evaluate_link_graph_foundation_frontier_accessibility
from .link_graph_foundation_frontier_artifacts import LinkGraphFoundationFrontierArtifactInventory, build_link_graph_foundation_frontier_artifacts
from .link_graph_foundation_frontier_bundle import LinkGraphFoundationFrontierBundle, build_link_graph_foundation_frontier_bundle
from .link_graph_foundation_frontier_checks import run_link_graph_foundation_frontier_invariants
from .link_graph_foundation_frontier_contracts import LinkGraphFoundationFrontierContractReport, build_link_graph_foundation_frontier_contracts
from .link_graph_foundation_frontier_depth import LinkGraphFoundationFrontierDepthReport, audit_link_graph_foundation_frontier_depth
from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation, evaluate_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_integrity import evaluate_link_graph_foundation_frontier_integrity
from .link_graph_foundation_frontier_lineage import LinkGraphFoundationFrontierLineage, build_link_graph_foundation_frontier_lineage
from .link_graph_foundation_frontier_metrics import LinkGraphFoundationFrontierMetrics, build_link_graph_foundation_frontier_metrics
from .link_graph_foundation_frontier_observability import LinkGraphFoundationFrontierObservabilityReport, build_link_graph_foundation_frontier_trace
from .link_graph_foundation_frontier_policy import LinkGraphFoundationFrontierPolicyReport, evaluate_link_graph_foundation_frontier_policy
from .link_graph_foundation_frontier_provenance import LinkGraphFoundationFrontierProvenanceGraph, build_link_graph_foundation_frontier_provenance
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierDataAudit, LinkGraphFoundationFrontierFixture, audit_link_graph_foundation_frontier_data, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_quality_gate import LinkGraphFoundationFrontierQualityReport, build_link_graph_foundation_frontier_quality
from .link_graph_foundation_frontier_reconciliation import LinkGraphFoundationFrontierReconciliation, reconcile_link_graph_foundation_frontier
from .link_graph_foundation_frontier_release import LinkGraphFoundationFrontierReleaseManifest, build_link_graph_foundation_frontier_release
from .link_graph_foundation_frontier_replay import LinkGraphFoundationFrontierReplayReport, replay_link_graph_foundation_frontier
from .link_graph_foundation_frontier_review_queue import LinkGraphFoundationFrontierReviewQueue, build_link_graph_foundation_frontier_review_queue
from .link_graph_foundation_frontier_scenario_matrix import LinkGraphFoundationFrontierScenarioMatrix, build_link_graph_foundation_frontier_scenario_matrix
from .link_graph_foundation_frontier_schema import LinkGraphFoundationFrontierSchemaReport, validate_link_graph_foundation_frontier_schema
from .link_graph_foundation_frontier_source_registry import LinkGraphFoundationFrontierSourceRegistry, build_link_graph_foundation_frontier_source_registry
from .link_graph_foundation_frontier_validation_matrix import LinkGraphFoundationFrontierValidationReport, build_link_graph_foundation_frontier_validation_matrix
from .link_graph_foundation_frontier_views import LinkGraphFoundationFrontierReviewView, build_link_graph_foundation_frontier_view
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierPipelineReport:
    run_id: str
    fixture: LinkGraphFoundationFrontierFixture
    data: LinkGraphFoundationFrontierDataAudit
    contracts: LinkGraphFoundationFrontierContractReport
    sources: LinkGraphFoundationFrontierSourceRegistry
    evaluation: LinkGraphFoundationFrontierEvaluation
    schema: LinkGraphFoundationFrontierSchemaReport
    metrics: LinkGraphFoundationFrontierMetrics
    lineage: LinkGraphFoundationFrontierLineage
    provenance: LinkGraphFoundationFrontierProvenanceGraph
    policy: LinkGraphFoundationFrontierPolicyReport
    reconciliation: LinkGraphFoundationFrontierReconciliation
    quality: LinkGraphFoundationFrontierQualityReport
    depth: LinkGraphFoundationFrontierDepthReport
    validation: LinkGraphFoundationFrontierValidationReport
    scenarios: LinkGraphFoundationFrontierScenarioMatrix
    accessibility: LinkGraphFoundationFrontierAccessibilityReport
    review_queue: LinkGraphFoundationFrontierReviewQueue
    view: LinkGraphFoundationFrontierReviewView
    integrity: Any
    release: LinkGraphFoundationFrontierReleaseManifest
    bundle: LinkGraphFoundationFrontierBundle
    artifacts: LinkGraphFoundationFrontierArtifactInventory
    replay: LinkGraphFoundationFrontierReplayReport
    trace: LinkGraphFoundationFrontierObservabilityReport
    invariants: Any
    stages: tuple[LinkGraphFoundationFrontierStage, ...]
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


def _stage(stage_id: str, passed: bool, inputs: int, outputs: int, detail: str) -> LinkGraphFoundationFrontierStage:
    return LinkGraphFoundationFrontierStage(stage_id, "passed" if passed else "failed", inputs, outputs, detail)


def run_link_graph_foundation_frontier_pipeline(fixture: LinkGraphFoundationFrontierFixture | None = None, *, run_id: str = "link-graph-foundation-frontier-run") -> LinkGraphFoundationFrontierPipelineReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    data = audit_link_graph_foundation_frontier_data(value)
    contracts = build_link_graph_foundation_frontier_contracts()
    sources = build_link_graph_foundation_frontier_source_registry(value)
    evaluation = evaluate_link_graph_foundation_frontier_fixture(value)
    schema = validate_link_graph_foundation_frontier_schema(value, evaluation)
    metrics = build_link_graph_foundation_frontier_metrics(evaluation, value)
    lineage = build_link_graph_foundation_frontier_lineage(value, evaluation)
    provenance = build_link_graph_foundation_frontier_provenance(value, evaluation)
    policy = evaluate_link_graph_foundation_frontier_policy(evaluation)
    reconciliation = reconcile_link_graph_foundation_frontier(evaluation)
    quality = build_link_graph_foundation_frontier_quality(value, data, schema, evaluation, reconciliation)
    depth = audit_link_graph_foundation_frontier_depth(value, evaluation)
    validation = build_link_graph_foundation_frontier_validation_matrix(evaluation)
    scenarios = build_link_graph_foundation_frontier_scenario_matrix(evaluation)
    accessibility = evaluate_link_graph_foundation_frontier_accessibility(value, evaluation)
    review_queue = build_link_graph_foundation_frontier_review_queue(evaluation, policy)
    view = build_link_graph_foundation_frontier_view(value, evaluation, review_queue)
    integrity = evaluate_link_graph_foundation_frontier_integrity(value, evaluation)
    release = build_link_graph_foundation_frontier_release(value, evaluation, quality)
    bundle = build_link_graph_foundation_frontier_bundle(value, release, metrics, lineage)
    artifacts = build_link_graph_foundation_frontier_artifacts(bundle, evaluation)
    replay = replay_link_graph_foundation_frontier(evaluation)
    trace = build_link_graph_foundation_frontier_trace(evaluation, run_id)
    invariants = run_link_graph_foundation_frontier_invariants(value, evaluation)
    stages = (_stage("fixture", data.accepted, 16, len(value.records), "fixture boundary"), _stage("contracts", contracts.accepted, 4, len(contracts.contracts), "operation contracts"), _stage("sources", sources.accepted, 5, len(sources.entries), "source closure"), _stage("replay", evaluation.accepted and replay.accepted, 16, len(evaluation.rows), "positive and control replay"), _stage("schema", schema.accepted, 16, len(schema.checks), "schema checks"), _stage("quality", quality.accepted, len(schema.checks), len(quality.checks), "quality floor"), _stage("policy", policy.accepted and lineage.accepted and provenance.accepted, 16, len(policy.decisions), "policy and provenance"), _stage("depth", depth.accepted, 16, len(depth.dimensions), "module depth"), _stage("validation", validation.accepted and scenarios.accepted, 16, len(validation.cells) + len(scenarios.scenarios), "validation matrices"), _stage("integrity", integrity.accepted and accessibility.accepted and invariants.accepted and reconciliation.accepted, 16, len(integrity.checks), "integrity and boundary"), _stage("release", release.publishable and bundle.accepted and artifacts.accepted, len(bundle.members), len(artifacts.artifacts), "release closure"), _stage("observability", trace.accepted and review_queue.accepted and view.accepted, 16, len(trace.events), "review observability"))
    accepted = all(item.status == "passed" for item in stages)
    return LinkGraphFoundationFrontierPipelineReport(run_id, value, data, contracts, sources, evaluation, schema, metrics, lineage, provenance, policy, reconciliation, quality, depth, validation, scenarios, accessibility, review_queue, view, integrity, release, bundle, artifacts, replay, trace, invariants, stages, accepted)


__all__ = ["LinkGraphFoundationFrontierPipelineReport", "LinkGraphFoundationFrontierStage", "run_link_graph_foundation_frontier_pipeline"]
