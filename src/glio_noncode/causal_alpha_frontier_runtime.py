"""Ordered 27-stage runtime for Domain 11 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierAdapterRegistry, build_causal_alpha_frontier_adapters
from .causal_alpha_frontier_artifacts import CausalAlphaFrontierArtifactInventory, build_causal_alpha_frontier_artifact_inventory
from .causal_alpha_frontier_assurance import CausalAlphaFrontierAssurance, build_causal_alpha_frontier_assurance
from .causal_alpha_frontier_bundle import CausalAlphaFrontierReleaseBundle, assemble_causal_alpha_frontier_bundle
from .causal_alpha_frontier_claim_boundary import CausalAlphaFrontierClaimBoundaryReport, build_causal_alpha_frontier_claim_boundary
from .causal_alpha_frontier_contracts import CausalAlphaFrontierContractReport, build_causal_alpha_frontier_contracts
from .causal_alpha_frontier_controls import CausalAlphaFrontierControlCoverage, build_causal_alpha_frontier_control_coverage
from .causal_alpha_frontier_depth import CausalAlphaFrontierDepthAudit, audit_causal_alpha_frontier_depth
from .causal_alpha_frontier_diagnostics import CausalAlphaFrontierDiagnosticReport, build_causal_alpha_frontier_diagnostics
from .causal_alpha_frontier_exports import CausalAlphaFrontierExportInventory, build_causal_alpha_frontier_exports
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation, evaluate_causal_alpha_frontier_fixture_deep
from .causal_alpha_frontier_integrity import CausalAlphaFrontierIntegrityReport, evaluate_causal_alpha_frontier_integrity
from .causal_alpha_frontier_lineage import CausalAlphaFrontierLineage, build_causal_alpha_frontier_lineage
from .causal_alpha_frontier_metrics import CausalAlphaFrontierMetrics, build_causal_alpha_frontier_metrics
from .causal_alpha_frontier_observability import CausalAlphaFrontierObservabilityReport, build_causal_alpha_frontier_observability, record_causal_alpha_frontier_event
from .causal_alpha_frontier_operational import CausalAlphaFrontierOperationalMatrix, build_causal_alpha_frontier_operational_matrix
from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision, CausalAlphaFrontierPolicy, default_causal_alpha_frontier_policy
from .causal_alpha_frontier_provenance import CausalAlphaFrontierProvenanceGraph, build_causal_alpha_frontier_provenance
from .causal_alpha_frontier_projections import CausalAlphaFrontierProjectionReport, build_causal_alpha_frontier_projections
from .causal_alpha_frontier_public_data import CausalAlphaFrontierDataAudit, CausalAlphaFrontierFixture, audit_causal_alpha_frontier_data, default_causal_alpha_frontier_fixture
from .causal_alpha_frontier_quality_gate import CausalAlphaFrontierQualityGate, evaluate_causal_alpha_frontier_quality
from .causal_alpha_frontier_reconciliation import CausalAlphaFrontierReconciliation, reconcile_causal_alpha_frontier
from .causal_alpha_frontier_release import CausalAlphaFrontierReleaseManifest, build_causal_alpha_frontier_release_manifest
from .causal_alpha_frontier_replay import CausalAlphaFrontierReplayReceipt, replay_causal_alpha_frontier
from .causal_alpha_frontier_review import CausalAlphaFrontierReviewQueue, build_causal_alpha_frontier_review_queue
from .causal_alpha_frontier_runbook import CausalAlphaFrontierRunbook, build_causal_alpha_frontier_runbook
from .causal_alpha_frontier_scenario_matrix import CausalAlphaFrontierScenarioMatrix, build_causal_alpha_frontier_scenario_matrix
from .causal_alpha_frontier_schema import CausalAlphaFrontierSchemaReport, validate_causal_alpha_frontier_schema
from .causal_alpha_frontier_traces import CausalAlphaFrontierTraceLedger, build_causal_alpha_frontier_trace_ledger
from .causal_alpha_frontier_validation_matrix import CausalAlphaFrontierValidationMatrix, build_causal_alpha_frontier_validation_matrix
from .causal_alpha_frontier_views import CausalAlphaFrontierReviewView, build_causal_alpha_frontier_review_view
from .causal_reasoning import CausalState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    output_address: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"stage_id": self.stage_id, "sequence": self.sequence, "state": self.state, "output_address": self.output_address, "detail": self.detail}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierRuntimeReport:
    run_id: str
    fixture: CausalAlphaFrontierFixture
    data_audit: CausalAlphaFrontierDataAudit
    adapters: CausalAlphaFrontierAdapterRegistry
    evaluation: CausalAlphaFrontierFixtureEvaluation
    controls: CausalAlphaFrontierControlCoverage
    contracts: CausalAlphaFrontierContractReport
    schema: CausalAlphaFrontierSchemaReport
    metrics: CausalAlphaFrontierMetrics
    lineage: CausalAlphaFrontierLineage
    provenance: CausalAlphaFrontierProvenanceGraph
    integrity: CausalAlphaFrontierIntegrityReport
    depth: CausalAlphaFrontierDepthAudit
    policy: CausalAlphaFrontierPolicy
    decisions: tuple[CausalAlphaFrontierDecision, ...]
    traces: CausalAlphaFrontierTraceLedger
    reconciliation: CausalAlphaFrontierReconciliation
    review: CausalAlphaFrontierReviewQueue
    projections: CausalAlphaFrontierProjectionReport
    diagnostics: CausalAlphaFrontierDiagnosticReport
    scenario: CausalAlphaFrontierScenarioMatrix
    validation: CausalAlphaFrontierValidationMatrix
    quality: CausalAlphaFrontierQualityGate
    bundle: CausalAlphaFrontierReleaseBundle
    release: CausalAlphaFrontierReleaseManifest
    artifacts: CausalAlphaFrontierArtifactInventory
    replay: CausalAlphaFrontierReplayReceipt
    operational: CausalAlphaFrontierOperationalMatrix
    boundary: CausalAlphaFrontierClaimBoundaryReport
    review_view: CausalAlphaFrontierReviewView
    exports: CausalAlphaFrontierExportInventory
    assurance: CausalAlphaFrontierAssurance
    runbook: CausalAlphaFrontierRunbook
    stages: tuple[CausalAlphaFrontierRuntimeStage, ...]
    observability: CausalAlphaFrontierObservabilityReport
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    @property
    def stage_count(self) -> int:
        return len(self.stages)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "run_id": self.run_id,
            "fixture": self.fixture.to_dict(),
            "data_audit": self.data_audit.to_dict(),
            "adapters": self.adapters.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "controls": self.controls.to_dict(),
            "contracts": self.contracts.to_dict(),
            "schema": self.schema.to_dict(),
            "metrics": self.metrics.to_dict(),
            "lineage": self.lineage.to_dict(),
            "provenance": self.provenance.to_dict(),
            "integrity": self.integrity.to_dict(),
            "depth": self.depth.to_dict(),
            "policy": self.policy.to_dict(),
            "decisions": [item.to_dict() for item in self.decisions],
            "traces": self.traces.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "review": self.review.to_dict(),
            "projections": self.projections.to_dict(),
            "diagnostics": self.diagnostics.to_dict(),
            "scenario": self.scenario.to_dict(),
            "validation": self.validation.to_dict(),
            "quality": self.quality.to_dict(),
            "bundle": self.bundle.to_dict(),
            "release": self.release.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "replay": self.replay.to_dict(),
            "operational": self.operational.to_dict(),
            "boundary": self.boundary.to_dict(),
            "review_view": self.review_view.to_dict(),
            "exports": self.exports.to_dict(),
            "assurance": self.assurance.to_dict(),
            "runbook": self.runbook.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "observability": self.observability.to_dict(),
            "stage_ids": self.stage_ids,
            "stage_count": self.stage_count,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_causal_alpha_frontier_runtime(fixture: CausalAlphaFrontierFixture | None = None, *, run_id: str = "causal-alpha-frontier-runtime") -> CausalAlphaFrontierRuntimeReport:
    value = fixture or default_causal_alpha_frontier_fixture()
    events: list[Any] = []
    stages: list[CausalAlphaFrontierRuntimeStage] = []

    def stage(stage_id: str, sequence: int, fn: Any, detail: str) -> Any:
        result, event = record_causal_alpha_frontier_event(run_id, sequence, stage_id, fn, detail)
        events.append(event)
        stages.append(CausalAlphaFrontierRuntimeStage(stage_id, sequence, event.state, event.output_address, detail))
        if result is None:
            raise RuntimeError(event.detail)
        return result

    data_audit = stage("data-audit", 1, lambda: audit_causal_alpha_frontier_data(value), "validate public sources and controls")
    adapters = stage("adapters", 2, build_causal_alpha_frontier_adapters, "bind four alpha operations")
    evaluation = stage("fixture-replay", 3, lambda: evaluate_causal_alpha_frontier_fixture_deep(value), "replay all sixteen controls")
    contracts = stage("contracts", 4, build_causal_alpha_frontier_contracts, "load capability contracts")
    schema = stage("schema", 5, lambda: validate_causal_alpha_frontier_schema(value, evaluation.evaluation, contracts), "validate record and output envelopes")
    metrics = stage("metrics", 6, lambda: build_causal_alpha_frontier_metrics(value, evaluation), "calculate operation metrics")
    lineage = stage("lineage", 7, lambda: build_causal_alpha_frontier_lineage(value, evaluation), "build source-to-result lineage")
    provenance = stage("provenance", 8, lambda: build_causal_alpha_frontier_provenance(value, evaluation, lineage), "build provenance graph")
    integrity = stage("integrity", 9, lambda: evaluate_causal_alpha_frontier_integrity(value, evaluation, lineage, provenance), "verify addresses and graph closure")
    depth = stage("depth-audit", 10, lambda: audit_causal_alpha_frontier_depth(value, evaluation, adapters, contracts, schema, metrics, lineage, provenance), "audit implementation depth")
    policy_base = stage("policy", 11, default_causal_alpha_frontier_policy, "load bounded disposition policy")
    decisions = stage("decisions", 12, lambda: policy_base.decide(evaluation), "produce one decision per row")
    policy = CausalAlphaFrontierPolicy(policy_base.policy_id, policy_base.version, decisions, policy_base.accepted)
    reconciliation = stage("reconciliation", 13, lambda: reconcile_causal_alpha_frontier(value, evaluation, decisions), "reconcile expected and observed states")
    review = stage("review-queue", 14, lambda: build_causal_alpha_frontier_review_queue(value, evaluation, decisions), "project review queue")
    controls = stage("control-coverage", 15, lambda: build_causal_alpha_frontier_control_coverage(value, evaluation, tuple(item.record_id for item in review.items)), "classify control coverage")
    traces = stage("decision-traces", 16, lambda: build_causal_alpha_frontier_trace_ledger(value, evaluation, decisions, review), "build per-row transformation traces")
    projections = stage("projections", 17, lambda: build_causal_alpha_frontier_projections(value, evaluation, controls, decisions), "build faceted review projections")
    diagnostics = stage("diagnostics", 18, lambda: build_causal_alpha_frontier_diagnostics(value, evaluation, controls, traces, projections), "run cross-plane release diagnostics")
    scenario = stage("scenario-matrix", 19, lambda: build_causal_alpha_frontier_scenario_matrix(value, evaluation), "build scenario matrix")
    validation = stage("validation-matrix", 20, lambda: build_causal_alpha_frontier_validation_matrix(value.fixture_id, evaluation.evaluation, contracts, metrics), "build capability validation matrix")
    quality = stage("quality-gate", 21, lambda: evaluate_causal_alpha_frontier_quality(value, evaluation.evaluation, contracts, schema, metrics, lineage, reconciliation, depth, review, decisions), "run quality gate")
    bundle = stage("release-bundle", 22, lambda: assemble_causal_alpha_frontier_bundle(value, evaluation, metrics, contracts, schema, lineage, depth, reconciliation, policy, decisions, review, quality, scenario, validation, bundle_id=run_id), "assemble release bundle")
    release = stage("release-manifest", 23, lambda: build_causal_alpha_frontier_release_manifest(bundle, quality, depth, review), "build release manifest")
    artifacts = stage("artifact-inventory", 24, lambda: build_causal_alpha_frontier_artifact_inventory(value, evaluation, bundle, release, controls, traces, projections, diagnostics), "enumerate release artifacts")
    replay = stage("deterministic-replay", 25, lambda: replay_causal_alpha_frontier(value, replay_id=run_id + ":replay"), "replay fixture twice")
    operational = stage("operational-matrix", 26, lambda: build_causal_alpha_frontier_operational_matrix(value, decisions, review), "project bounded operational actions")
    boundary = stage("claim-boundary", 27, lambda: build_causal_alpha_frontier_claim_boundary(bundle, operational), "enforce allowed and excluded uses")
    review_view = stage("review-view", 28, lambda: build_causal_alpha_frontier_review_view(value, evaluation, decisions, reconciliation, review), "build stable review table")
    exports = stage("exports", 29, lambda: build_causal_alpha_frontier_exports(value, evaluation, review_view, bundle, release, artifacts, controls, traces, projections, diagnostics), "assemble canonical exports")
    assurance = stage("assurance", 30, lambda: build_causal_alpha_frontier_assurance(release, replay, integrity, operational, boundary, exports, artifacts), "assemble assurance statement")
    runbook = stage("runbook", 31, lambda: build_causal_alpha_frontier_runbook(run_id, value.fixture_id, 31, release, bundle, boundary, assurance), "publish executable release runbook")
    observability = build_causal_alpha_frontier_observability(run_id, tuple(events))
    accepted = bool(data_audit.accepted and adapters.accepted and evaluation.accepted and controls.accepted and traces.accepted and projections.accepted and diagnostics.accepted and schema.accepted and integrity.accepted and depth.accepted and reconciliation.accepted and quality.accepted and bundle.publishable and release.accepted and artifacts.accepted and replay.deterministic and operational.accepted and boundary.accepted and review_view.accepted and exports.accepted and assurance.accepted and runbook.accepted and observability.accepted)
    return CausalAlphaFrontierRuntimeReport(run_id, value, data_audit, adapters, evaluation, controls, contracts, schema, metrics, lineage, provenance, integrity, depth, policy, decisions, traces, reconciliation, review, projections, diagnostics, scenario, validation, quality, bundle, release, artifacts, replay, operational, boundary, review_view, exports, assurance, runbook, tuple(stages), observability, accepted)


__all__ = ["CausalAlphaFrontierRuntimeReport", "CausalAlphaFrontierRuntimeStage", "run_causal_alpha_frontier_runtime"]
