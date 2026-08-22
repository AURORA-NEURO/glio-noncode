"""Twelve-stage executable pipeline for Domain 10 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_accessibility import LinkGraphAlphaFrontierAccessibilityReport, evaluate_link_graph_alpha_frontier_accessibility
from .link_graph_alpha_frontier_artifacts import LinkGraphAlphaFrontierArtifactInventory, build_link_graph_alpha_frontier_artifacts
from .link_graph_alpha_frontier_bundle import LinkGraphAlphaFrontierBundle, build_link_graph_alpha_frontier_bundle
from .link_graph_alpha_frontier_candidate_depth import LinkGraphAlphaFrontierCandidateDepthReport, audit_link_graph_alpha_frontier_candidates
from .link_graph_alpha_frontier_checks import LinkGraphAlphaFrontierInvariantReport, run_link_graph_alpha_frontier_invariants
from .link_graph_alpha_frontier_compliance import LinkGraphAlphaFrontierBoundaryReport, evaluate_link_graph_alpha_frontier_boundary
from .link_graph_alpha_frontier_contracts import LinkGraphAlphaFrontierContractReport, build_link_graph_alpha_frontier_contracts
from .link_graph_alpha_frontier_delta_depth import LinkGraphAlphaFrontierDeltaDepthReport, audit_link_graph_alpha_frontier_deltas
from .link_graph_alpha_frontier_depth import LinkGraphAlphaFrontierDepthReport, audit_link_graph_alpha_frontier_depth
from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation, evaluate_link_graph_alpha_frontier_fixture
from .link_graph_alpha_frontier_integrity import LinkGraphAlphaFrontierIntegrityReport, evaluate_link_graph_alpha_frontier_integrity
from .link_graph_alpha_frontier_lineage import LinkGraphAlphaFrontierLineage, build_link_graph_alpha_frontier_lineage
from .link_graph_alpha_frontier_metrics import LinkGraphAlphaFrontierMetrics, build_link_graph_alpha_frontier_metrics
from .link_graph_alpha_frontier_observability import LinkGraphAlphaFrontierObservabilityReport, build_link_graph_alpha_frontier_trace
from .link_graph_alpha_frontier_policy import LinkGraphAlphaFrontierPolicyReport, evaluate_link_graph_alpha_frontier_policy
from .link_graph_alpha_frontier_provenance import LinkGraphAlphaFrontierProvenanceGraph, build_link_graph_alpha_frontier_provenance
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierDataAudit, LinkGraphAlphaFrontierFixture, audit_link_graph_alpha_frontier_data, default_link_graph_alpha_frontier_fixture
from .link_graph_alpha_frontier_quality_gate import LinkGraphAlphaFrontierQualityReport, build_link_graph_alpha_frontier_quality
from .link_graph_alpha_frontier_reconciliation import LinkGraphAlphaFrontierReconciliation, reconcile_link_graph_alpha_frontier
from .link_graph_alpha_frontier_release import LinkGraphAlphaFrontierReleaseManifest, build_link_graph_alpha_frontier_release
from .link_graph_alpha_frontier_review_queue import LinkGraphAlphaFrontierReviewQueue, build_link_graph_alpha_frontier_review_queue
from .link_graph_alpha_frontier_scenario_matrix import LinkGraphAlphaFrontierScenarioMatrix, build_link_graph_alpha_frontier_scenario_matrix
from .link_graph_alpha_frontier_schema import LinkGraphAlphaFrontierSchemaReport, validate_link_graph_alpha_frontier_schema
from .link_graph_alpha_frontier_source_registry import LinkGraphAlphaFrontierSourceRegistry, build_link_graph_alpha_frontier_source_registry
from .link_graph_alpha_frontier_validation_matrix import LinkGraphAlphaFrontierValidationReport, build_link_graph_alpha_frontier_validation_matrix
from .link_graph_alpha_frontier_views import LinkGraphAlphaFrontierReviewView, build_link_graph_alpha_frontier_view
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierPipelineReport:
    run_id: str
    fixture: LinkGraphAlphaFrontierFixture
    data: LinkGraphAlphaFrontierDataAudit
    contracts: LinkGraphAlphaFrontierContractReport
    sources: LinkGraphAlphaFrontierSourceRegistry
    evaluation: LinkGraphAlphaFrontierEvaluation
    schema: LinkGraphAlphaFrontierSchemaReport
    metrics: LinkGraphAlphaFrontierMetrics
    lineage: LinkGraphAlphaFrontierLineage
    provenance: LinkGraphAlphaFrontierProvenanceGraph
    policy: LinkGraphAlphaFrontierPolicyReport
    reconciliation: LinkGraphAlphaFrontierReconciliation
    quality: LinkGraphAlphaFrontierQualityReport
    depth: LinkGraphAlphaFrontierDepthReport
    candidates: LinkGraphAlphaFrontierCandidateDepthReport
    deltas: LinkGraphAlphaFrontierDeltaDepthReport
    validation: LinkGraphAlphaFrontierValidationReport
    scenarios: LinkGraphAlphaFrontierScenarioMatrix
    accessibility: LinkGraphAlphaFrontierAccessibilityReport
    review_queue: LinkGraphAlphaFrontierReviewQueue
    view: LinkGraphAlphaFrontierReviewView
    integrity: LinkGraphAlphaFrontierIntegrityReport
    boundary: LinkGraphAlphaFrontierBoundaryReport
    release: LinkGraphAlphaFrontierReleaseManifest
    bundle: LinkGraphAlphaFrontierBundle
    artifacts: LinkGraphAlphaFrontierArtifactInventory
    trace: LinkGraphAlphaFrontierObservabilityReport
    invariants: LinkGraphAlphaFrontierInvariantReport
    stages: tuple[LinkGraphAlphaFrontierStage, ...]
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


def _stage(stage_id: str, passed: bool, input_count: int, output_count: int, detail: str) -> LinkGraphAlphaFrontierStage:
    return LinkGraphAlphaFrontierStage(stage_id, "passed" if passed else "failed", input_count, output_count, detail)


def run_link_graph_alpha_frontier_pipeline(fixture: LinkGraphAlphaFrontierFixture | None = None, *, run_id: str = "link-graph-alpha-frontier-run") -> LinkGraphAlphaFrontierPipelineReport:
    value = fixture or default_link_graph_alpha_frontier_fixture()
    data = audit_link_graph_alpha_frontier_data(value)
    contracts = build_link_graph_alpha_frontier_contracts()
    sources = build_link_graph_alpha_frontier_source_registry(value)
    evaluation = evaluate_link_graph_alpha_frontier_fixture(value)
    schema = validate_link_graph_alpha_frontier_schema(value, evaluation)
    metrics = build_link_graph_alpha_frontier_metrics(evaluation, value)
    lineage = build_link_graph_alpha_frontier_lineage(value, evaluation)
    provenance = build_link_graph_alpha_frontier_provenance(value, evaluation)
    policy = evaluate_link_graph_alpha_frontier_policy(evaluation)
    reconciliation = reconcile_link_graph_alpha_frontier(evaluation)
    quality = build_link_graph_alpha_frontier_quality(value, data, schema, evaluation, reconciliation)
    depth = audit_link_graph_alpha_frontier_depth(value, evaluation)
    candidates = audit_link_graph_alpha_frontier_candidates(evaluation)
    deltas = audit_link_graph_alpha_frontier_deltas(value, evaluation)
    validation = build_link_graph_alpha_frontier_validation_matrix(evaluation)
    scenarios = build_link_graph_alpha_frontier_scenario_matrix(evaluation)
    accessibility = evaluate_link_graph_alpha_frontier_accessibility(value, evaluation)
    review_queue = build_link_graph_alpha_frontier_review_queue(evaluation, policy)
    view = build_link_graph_alpha_frontier_view(value, evaluation, review_queue)
    integrity = evaluate_link_graph_alpha_frontier_integrity(value, evaluation)
    boundary = evaluate_link_graph_alpha_frontier_boundary(value, evaluation)
    release = build_link_graph_alpha_frontier_release(value, evaluation, quality)
    bundle = build_link_graph_alpha_frontier_bundle(value, release, metrics, deltas)
    artifacts = build_link_graph_alpha_frontier_artifacts(bundle, evaluation)
    trace = build_link_graph_alpha_frontier_trace(evaluation, run_id)
    invariants = run_link_graph_alpha_frontier_invariants(value, evaluation)
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
    return LinkGraphAlphaFrontierPipelineReport(run_id, value, data, contracts, sources, evaluation, schema, metrics, lineage, provenance, policy, reconciliation, quality, depth, candidates, deltas, validation, scenarios, accessibility, review_queue, view, integrity, boundary, release, bundle, artifacts, trace, invariants, stages, accepted)


__all__ = ["LinkGraphAlphaFrontierPipelineReport", "LinkGraphAlphaFrontierStage", "run_link_graph_alpha_frontier_pipeline"]
