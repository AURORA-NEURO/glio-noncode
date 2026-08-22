"""Twelve-stage release pipeline for Domain 09 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_accessibility import TopologyAlphaFrontierAccessibilityReport, evaluate_topology_alpha_frontier_accessibility
from .topology_alpha_frontier_artifacts import TopologyAlphaFrontierArtifactInventory, build_topology_alpha_frontier_artifacts
from .topology_alpha_frontier_bundle import TopologyAlphaFrontierBundle, build_topology_alpha_frontier_bundle
from .topology_alpha_frontier_candidate_depth import TopologyAlphaFrontierCandidateDepthReport, audit_topology_alpha_frontier_candidates
from .topology_alpha_frontier_checks import TopologyAlphaFrontierInvariantReport, run_topology_alpha_frontier_invariants
from .topology_alpha_frontier_compliance import TopologyAlphaFrontierBoundaryReport, evaluate_topology_alpha_frontier_boundary
from .topology_alpha_frontier_contracts import TopologyAlphaFrontierContractReport, build_topology_alpha_frontier_contracts
from .topology_alpha_frontier_delta_depth import TopologyAlphaFrontierDeltaDepthReport, audit_topology_alpha_frontier_deltas
from .topology_alpha_frontier_depth import TopologyAlphaFrontierDepthReport, audit_topology_alpha_frontier_depth
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation, evaluate_topology_alpha_frontier_fixture
from .topology_alpha_frontier_integrity import TopologyAlphaFrontierIntegrityReport, evaluate_topology_alpha_frontier_integrity
from .topology_alpha_frontier_lineage import TopologyAlphaFrontierLineage, build_topology_alpha_frontier_lineage
from .topology_alpha_frontier_metrics import TopologyAlphaFrontierMetrics, build_topology_alpha_frontier_metrics
from .topology_alpha_frontier_observability import TopologyAlphaFrontierObservabilityReport, build_topology_alpha_frontier_trace
from .topology_alpha_frontier_policy import TopologyAlphaFrontierPolicyReport, evaluate_topology_alpha_frontier_policy
from .topology_alpha_frontier_provenance import TopologyAlphaFrontierProvenanceGraph, build_topology_alpha_frontier_provenance
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierDataAudit, TopologyAlphaFrontierFixture, audit_topology_alpha_frontier_data, default_topology_alpha_frontier_fixture
from .topology_alpha_frontier_quality_gate import TopologyAlphaFrontierQualityReport, build_topology_alpha_frontier_quality
from .topology_alpha_frontier_reconciliation import TopologyAlphaFrontierReconciliation, reconcile_topology_alpha_frontier
from .topology_alpha_frontier_release import TopologyAlphaFrontierReleaseManifest, build_topology_alpha_frontier_release
from .topology_alpha_frontier_review_queue import TopologyAlphaFrontierReviewQueue, build_topology_alpha_frontier_review_queue
from .topology_alpha_frontier_scenario_matrix import TopologyAlphaFrontierScenarioMatrix, build_topology_alpha_frontier_scenario_matrix
from .topology_alpha_frontier_schema import TopologyAlphaFrontierSchemaReport, validate_topology_alpha_frontier_schema
from .topology_alpha_frontier_source_registry import TopologyAlphaFrontierSourceRegistry, build_topology_alpha_frontier_source_registry
from .topology_alpha_frontier_validation_matrix import TopologyAlphaFrontierValidationReport, build_topology_alpha_frontier_validation_matrix
from .topology_alpha_frontier_views import TopologyAlphaFrontierReviewView, build_topology_alpha_frontier_view


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierPipelineReport:
    run_id: str
    fixture: TopologyAlphaFrontierFixture
    data: TopologyAlphaFrontierDataAudit
    contracts: TopologyAlphaFrontierContractReport
    sources: TopologyAlphaFrontierSourceRegistry
    evaluation: TopologyAlphaFrontierEvaluation
    schema: TopologyAlphaFrontierSchemaReport
    metrics: TopologyAlphaFrontierMetrics
    lineage: TopologyAlphaFrontierLineage
    provenance: TopologyAlphaFrontierProvenanceGraph
    policy: TopologyAlphaFrontierPolicyReport
    reconciliation: TopologyAlphaFrontierReconciliation
    quality: TopologyAlphaFrontierQualityReport
    depth: TopologyAlphaFrontierDepthReport
    candidates: TopologyAlphaFrontierCandidateDepthReport
    deltas: TopologyAlphaFrontierDeltaDepthReport
    validation: TopologyAlphaFrontierValidationReport
    scenarios: TopologyAlphaFrontierScenarioMatrix
    accessibility: TopologyAlphaFrontierAccessibilityReport
    review_queue: TopologyAlphaFrontierReviewQueue
    view: TopologyAlphaFrontierReviewView
    integrity: TopologyAlphaFrontierIntegrityReport
    boundary: TopologyAlphaFrontierBoundaryReport
    release: TopologyAlphaFrontierReleaseManifest
    bundle: TopologyAlphaFrontierBundle
    artifacts: TopologyAlphaFrontierArtifactInventory
    trace: TopologyAlphaFrontierObservabilityReport
    invariants: TopologyAlphaFrontierInvariantReport
    stages: tuple[TopologyAlphaFrontierStage, ...]
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


def _stage(stage_id: str, passed: bool, input_count: int, output_count: int, detail: str) -> TopologyAlphaFrontierStage:
    return TopologyAlphaFrontierStage(stage_id, "passed" if passed else "failed", input_count, output_count, detail)


def run_topology_alpha_frontier_pipeline(fixture: TopologyAlphaFrontierFixture | None = None, *, run_id: str = "topology-alpha-frontier-run") -> TopologyAlphaFrontierPipelineReport:
    value = fixture or default_topology_alpha_frontier_fixture()
    data = audit_topology_alpha_frontier_data(value)
    contracts = build_topology_alpha_frontier_contracts()
    sources = build_topology_alpha_frontier_source_registry(value)
    evaluation = evaluate_topology_alpha_frontier_fixture(value)
    schema = validate_topology_alpha_frontier_schema(value, evaluation)
    metrics = build_topology_alpha_frontier_metrics(evaluation)
    lineage = build_topology_alpha_frontier_lineage(value, evaluation)
    provenance = build_topology_alpha_frontier_provenance(value, evaluation)
    policy = evaluate_topology_alpha_frontier_policy(evaluation)
    reconciliation = reconcile_topology_alpha_frontier(evaluation)
    quality = build_topology_alpha_frontier_quality(value, data, schema, evaluation, reconciliation)
    depth = audit_topology_alpha_frontier_depth(value, evaluation)
    candidates = audit_topology_alpha_frontier_candidates(evaluation)
    deltas = audit_topology_alpha_frontier_deltas(evaluation)
    validation = build_topology_alpha_frontier_validation_matrix(evaluation)
    scenarios = build_topology_alpha_frontier_scenario_matrix(evaluation)
    accessibility = evaluate_topology_alpha_frontier_accessibility(evaluation)
    review_queue = build_topology_alpha_frontier_review_queue(evaluation)
    view = build_topology_alpha_frontier_view(evaluation)
    integrity = evaluate_topology_alpha_frontier_integrity(value, evaluation)
    boundary = evaluate_topology_alpha_frontier_boundary(value, evaluation)
    release = build_topology_alpha_frontier_release(value, evaluation, quality)
    bundle = build_topology_alpha_frontier_bundle(value, release, metrics, deltas)
    artifacts = build_topology_alpha_frontier_artifacts(bundle, evaluation)
    trace = build_topology_alpha_frontier_trace(evaluation, run_id)
    invariants = run_topology_alpha_frontier_invariants(value, evaluation)
    stages = (_stage("fixture", data.accepted, 16, len(value.records), "fixture and aggregate boundary"), _stage("contracts", contracts.accepted, 4, len(contracts.contracts), "typed operation contracts"), _stage("sources", sources.accepted, len(value.sources), len(sources.entries), "source receipt closure"), _stage("evaluation", evaluation.accepted, len(value.records), len(evaluation.rows), "positive and control replay"), _stage("schema", schema.accepted, len(evaluation.rows), len(schema.checks), "schema and envelope checks"), _stage("quality", quality.accepted, len(schema.checks), len(quality.checks), "quality floor"), _stage("policy", policy.accepted and lineage.accepted and provenance.accepted, len(evaluation.rows), len(policy.decisions), "review policy and provenance"), _stage("depth", depth.accepted and candidates.accepted and deltas.accepted, len(evaluation.rows), len(depth.dimensions) + len(candidates.observations) + len(deltas.observations), "depth, candidate, and delta audits"), _stage("validation", validation.accepted and scenarios.accepted, len(evaluation.rows), len(validation.cells) + len(scenarios.scenarios), "matrix and scenario coverage"), _stage("integrity", integrity.accepted and boundary.accepted and accessibility.accepted and invariants.accepted and reconciliation.accepted, len(evaluation.rows), len(integrity.checks) + len(boundary.checks) + len(invariants.results), "boundary, integrity, and accessibility"), _stage("release", release.publishable and bundle.accepted and artifacts.accepted, len(bundle.members), len(artifacts.artifacts), "release bundle and artifact inventory"), _stage("observability", trace.accepted and view.accepted and review_queue.accepted, len(evaluation.rows), len(trace.events), "trace, view, and review queue"))
    accepted = all(item.status == "passed" for item in stages) and evaluation.accepted and quality.accepted and release.publishable
    return TopologyAlphaFrontierPipelineReport(run_id, value, data, contracts, sources, evaluation, schema, metrics, lineage, provenance, policy, reconciliation, quality, depth, candidates, deltas, validation, scenarios, accessibility, review_queue, view, integrity, boundary, release, bundle, artifacts, trace, invariants, stages, accepted)


__all__ = ["TopologyAlphaFrontierPipelineReport", "TopologyAlphaFrontierStage", "run_topology_alpha_frontier_pipeline"]
