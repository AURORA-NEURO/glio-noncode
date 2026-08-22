"""Twelve-stage release pipeline for Domain 09 C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_accessibility import TopologyBetaFrontierAccessibilityReport, evaluate_topology_beta_frontier_accessibility
from .topology_beta_frontier_artifacts import TopologyBetaFrontierArtifactInventory, build_topology_beta_frontier_artifacts
from .topology_beta_frontier_bundle import TopologyBetaFrontierBundle, build_topology_beta_frontier_bundle
from .topology_beta_frontier_candidate_depth import TopologyBetaFrontierCandidateDepthReport, audit_topology_beta_frontier_candidates
from .topology_beta_frontier_checks import TopologyBetaFrontierInvariantReport, run_topology_beta_frontier_invariants
from .topology_beta_frontier_compliance import TopologyBetaFrontierBoundaryReport, evaluate_topology_beta_frontier_boundary
from .topology_beta_frontier_contracts import TopologyBetaFrontierContractReport, build_topology_beta_frontier_contracts
from .topology_beta_frontier_delta_depth import TopologyBetaFrontierDeltaDepthReport, audit_topology_beta_frontier_deltas
from .topology_beta_frontier_depth import TopologyBetaFrontierDepthReport, audit_topology_beta_frontier_depth
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation, evaluate_topology_beta_frontier_fixture
from .topology_beta_frontier_integrity import TopologyBetaFrontierIntegrityReport, evaluate_topology_beta_frontier_integrity
from .topology_beta_frontier_lineage import TopologyBetaFrontierLineage, build_topology_beta_frontier_lineage
from .topology_beta_frontier_metrics import TopologyBetaFrontierMetrics, build_topology_beta_frontier_metrics
from .topology_beta_frontier_observability import TopologyBetaFrontierObservabilityReport, build_topology_beta_frontier_trace
from .topology_beta_frontier_policy import TopologyBetaFrontierPolicyReport, evaluate_topology_beta_frontier_policy
from .topology_beta_frontier_provenance import TopologyBetaFrontierProvenanceGraph, build_topology_beta_frontier_provenance
from .topology_beta_frontier_public_data import TopologyBetaFrontierDataAudit, TopologyBetaFrontierFixture, audit_topology_beta_frontier_data, default_topology_beta_frontier_fixture
from .topology_beta_frontier_quality_gate import TopologyBetaFrontierQualityReport, build_topology_beta_frontier_quality
from .topology_beta_frontier_reconciliation import TopologyBetaFrontierReconciliation, reconcile_topology_beta_frontier
from .topology_beta_frontier_release import TopologyBetaFrontierReleaseManifest, build_topology_beta_frontier_release
from .topology_beta_frontier_review_queue import TopologyBetaFrontierReviewQueue, build_topology_beta_frontier_review_queue
from .topology_beta_frontier_scenario_matrix import TopologyBetaFrontierScenarioMatrix, build_topology_beta_frontier_scenario_matrix
from .topology_beta_frontier_schema import TopologyBetaFrontierSchemaReport, validate_topology_beta_frontier_schema
from .topology_beta_frontier_source_registry import TopologyBetaFrontierSourceRegistry, build_topology_beta_frontier_source_registry
from .topology_beta_frontier_validation_matrix import TopologyBetaFrontierValidationReport, build_topology_beta_frontier_validation_matrix
from .topology_beta_frontier_views import TopologyBetaFrontierReviewView, build_topology_beta_frontier_view


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierPipelineReport:
    run_id: str
    fixture: TopologyBetaFrontierFixture
    data: TopologyBetaFrontierDataAudit
    contracts: TopologyBetaFrontierContractReport
    sources: TopologyBetaFrontierSourceRegistry
    evaluation: TopologyBetaFrontierEvaluation
    schema: TopologyBetaFrontierSchemaReport
    metrics: TopologyBetaFrontierMetrics
    lineage: TopologyBetaFrontierLineage
    provenance: TopologyBetaFrontierProvenanceGraph
    policy: TopologyBetaFrontierPolicyReport
    reconciliation: TopologyBetaFrontierReconciliation
    quality: TopologyBetaFrontierQualityReport
    depth: TopologyBetaFrontierDepthReport
    candidates: TopologyBetaFrontierCandidateDepthReport
    deltas: TopologyBetaFrontierDeltaDepthReport
    validation: TopologyBetaFrontierValidationReport
    scenarios: TopologyBetaFrontierScenarioMatrix
    accessibility: TopologyBetaFrontierAccessibilityReport
    review_queue: TopologyBetaFrontierReviewQueue
    view: TopologyBetaFrontierReviewView
    integrity: TopologyBetaFrontierIntegrityReport
    boundary: TopologyBetaFrontierBoundaryReport
    release: TopologyBetaFrontierReleaseManifest
    bundle: TopologyBetaFrontierBundle
    artifacts: TopologyBetaFrontierArtifactInventory
    trace: TopologyBetaFrontierObservabilityReport
    invariants: TopologyBetaFrontierInvariantReport
    stages: tuple[TopologyBetaFrontierStage, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"run_id": self.run_id, "fixture": self.fixture.content_address, "stages": self.stages, "accepted": self.accepted}))

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages if item.status != "passed")

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "fixture": self.fixture.to_dict(False), "data": self.data.to_dict(), "contracts": self.contracts.to_dict(), "sources": self.sources.to_dict(), "evaluation": self.evaluation.to_dict(), "schema": self.schema.to_dict(), "metrics": self.metrics.to_dict(), "lineage": self.lineage.to_dict(), "provenance": self.provenance.to_dict(), "policy": self.policy.to_dict(), "reconciliation": self.reconciliation.to_dict(), "quality": self.quality.to_dict(), "depth": self.depth.to_dict(), "candidates": self.candidates.to_dict(), "deltas": self.deltas.to_dict(), "validation": self.validation.to_dict(), "scenarios": self.scenarios.to_dict(), "accessibility": self.accessibility.to_dict(), "review_queue": self.review_queue.to_dict(), "view": self.view.to_dict(), "integrity": self.integrity.to_dict(), "boundary": self.boundary.to_dict(), "release": self.release.to_dict(), "bundle": self.bundle.to_dict(), "artifacts": self.artifacts.to_dict(), "trace": self.trace.to_dict(), "invariants": self.invariants.to_dict(), "stages": [item.to_dict() for item in self.stages], "failed_stages": self.failed_stages, "accepted": self.accepted, "content_address": self.content_address}


def _stage(stage_id: str, passed: bool, input_count: int, output_count: int, detail: str) -> TopologyBetaFrontierStage:
    return TopologyBetaFrontierStage(stage_id, "passed" if passed else "failed", input_count, output_count, detail)


def run_topology_beta_frontier_pipeline(fixture: TopologyBetaFrontierFixture | None = None, *, run_id: str = "topology-beta-frontier-run") -> TopologyBetaFrontierPipelineReport:
    value = fixture or default_topology_beta_frontier_fixture()
    data = audit_topology_beta_frontier_data(value)
    contracts = build_topology_beta_frontier_contracts()
    sources = build_topology_beta_frontier_source_registry(value)
    evaluation = evaluate_topology_beta_frontier_fixture(value)
    schema = validate_topology_beta_frontier_schema(value, evaluation)
    metrics = build_topology_beta_frontier_metrics(evaluation)
    lineage = build_topology_beta_frontier_lineage(value, evaluation)
    provenance = build_topology_beta_frontier_provenance(value, evaluation)
    policy = evaluate_topology_beta_frontier_policy(evaluation)
    reconciliation = reconcile_topology_beta_frontier(evaluation)
    quality = build_topology_beta_frontier_quality(value, data, schema, evaluation, reconciliation)
    depth = audit_topology_beta_frontier_depth(value, evaluation)
    candidates = audit_topology_beta_frontier_candidates(evaluation)
    deltas = audit_topology_beta_frontier_deltas(evaluation)
    validation = build_topology_beta_frontier_validation_matrix(evaluation)
    scenarios = build_topology_beta_frontier_scenario_matrix(evaluation)
    accessibility = evaluate_topology_beta_frontier_accessibility(evaluation)
    review_queue = build_topology_beta_frontier_review_queue(evaluation)
    view = build_topology_beta_frontier_view(evaluation)
    integrity = evaluate_topology_beta_frontier_integrity(value, evaluation)
    boundary = evaluate_topology_beta_frontier_boundary(value, evaluation)
    release = build_topology_beta_frontier_release(value, evaluation, quality)
    bundle = build_topology_beta_frontier_bundle(value, release, metrics, deltas)
    artifacts = build_topology_beta_frontier_artifacts(bundle, evaluation)
    trace = build_topology_beta_frontier_trace(evaluation, run_id)
    invariants = run_topology_beta_frontier_invariants(value, evaluation)
    stages = (
        _stage("fixture", data.accepted, 16, len(value.records), "fixture and aggregate boundary"),
        _stage("contracts", contracts.accepted, 4, len(contracts.contracts), "typed operation contracts"),
        _stage("sources", sources.accepted, len(value.sources), len(sources.entries), "source receipt closure"),
        _stage("evaluation", evaluation.accepted, len(value.records), len(evaluation.rows), "positive and control replay"),
        _stage("schema", schema.accepted, len(evaluation.rows), len(schema.checks), "schema and envelope checks"),
        _stage("quality", quality.accepted, len(schema.checks), len(quality.checks), "quality floor"),
        _stage("policy", policy.accepted and lineage.accepted and provenance.accepted, len(evaluation.rows), len(policy.decisions), "review policy and provenance"),
        _stage("depth", depth.accepted and candidates.accepted and deltas.accepted, len(evaluation.rows), len(depth.dimensions) + len(candidates.observations) + len(deltas.observations), "depth, candidate, and delta audits"),
        _stage("validation", validation.accepted and scenarios.accepted, len(evaluation.rows), len(validation.cells) + len(scenarios.scenarios), "matrix and scenario coverage"),
        _stage("integrity", integrity.accepted and boundary.accepted and accessibility.accepted and invariants.accepted and reconciliation.accepted, len(evaluation.rows), len(integrity.checks) + len(boundary.checks) + len(invariants.results), "boundary, integrity, and accessibility"),
        _stage("release", release.publishable and bundle.accepted and artifacts.accepted, len(bundle.members), len(artifacts.artifacts), "release bundle and artifact inventory"),
        _stage("observability", trace.accepted and view.accepted and review_queue.accepted, len(evaluation.rows), len(trace.events), "trace, view, and review queue"),
    )
    accepted = all(item.status == "passed" for item in stages) and evaluation.accepted and quality.accepted and release.publishable
    return TopologyBetaFrontierPipelineReport(run_id, value, data, contracts, sources, evaluation, schema, metrics, lineage, provenance, policy, reconciliation, quality, depth, candidates, deltas, validation, scenarios, accessibility, review_queue, view, integrity, boundary, release, bundle, artifacts, trace, invariants, stages, accepted)


__all__ = ["TopologyBetaFrontierPipelineReport", "TopologyBetaFrontierStage", "run_topology_beta_frontier_pipeline"]
