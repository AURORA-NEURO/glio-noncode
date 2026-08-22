"""Ordered release rehearsal for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_adapters import CausalBetaFrontierAdapterRegistry, build_causal_beta_frontier_adapters
from .causal_beta_frontier_artifacts import CausalBetaFrontierArtifactInventory, build_causal_beta_frontier_artifact_inventory
from .causal_beta_frontier_assurance import CausalBetaFrontierAssurance, build_causal_beta_frontier_assurance
from .causal_beta_frontier_bundle import CausalBetaFrontierReleaseBundle, assemble_causal_beta_frontier_bundle
from .causal_beta_frontier_claim_boundary import CausalBetaFrontierClaimBoundaryReport, build_causal_beta_frontier_claim_boundary
from .causal_beta_frontier_contracts import CausalBetaFrontierContractReport, build_causal_beta_frontier_contracts
from .causal_beta_frontier_depth import CausalBetaFrontierDepthAudit, audit_causal_beta_frontier_depth
from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation, evaluate_causal_beta_frontier_fixture
from .causal_beta_frontier_exports import CausalBetaFrontierExportInventory, build_causal_beta_frontier_exports
from .causal_beta_frontier_integrity import CausalBetaFrontierIntegrityReport, evaluate_causal_beta_frontier_integrity
from .causal_beta_frontier_lineage import CausalBetaFrontierLineage, build_causal_beta_frontier_lineage
from .causal_beta_frontier_metrics import CausalBetaFrontierMetrics, build_causal_beta_frontier_metrics
from .causal_beta_frontier_observability import build_causal_beta_frontier_observability, record_causal_beta_frontier_event
from .causal_beta_frontier_policy import CausalBetaFrontierPolicy, default_causal_beta_frontier_policy
from .causal_beta_frontier_provenance import CausalBetaFrontierProvenanceGraph, build_causal_beta_frontier_provenance
from .causal_beta_frontier_quality_gate import CausalBetaFrontierQualityGate, evaluate_causal_beta_frontier_quality
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, audit_causal_beta_frontier_data, default_causal_beta_frontier_fixture
from .causal_beta_frontier_operational import CausalBetaFrontierOperationalMatrix, build_causal_beta_frontier_operational_matrix
from .causal_beta_frontier_reconciliation import CausalBetaFrontierReconciliation, reconcile_causal_beta_frontier
from .causal_beta_frontier_release import CausalBetaFrontierReleaseManifest, build_causal_beta_frontier_release_manifest
from .causal_beta_frontier_replay import CausalBetaFrontierReplayReceipt, replay_causal_beta_frontier
from .causal_beta_frontier_runbook import CausalBetaFrontierRunbook, build_causal_beta_frontier_runbook
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue, build_causal_beta_frontier_review_queue
from .causal_beta_frontier_scenario_matrix import CausalBetaFrontierScenarioMatrix, build_causal_beta_frontier_scenario_matrix
from .causal_beta_frontier_schema import CausalBetaFrontierSchemaReport, validate_causal_beta_frontier_schema
from .causal_beta_frontier_validation_matrix import CausalBetaFrontierValidationMatrix, build_causal_beta_frontier_validation_matrix
from .causal_beta_frontier_views import CausalBetaFrontierReviewView, build_causal_beta_frontier_review_view
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierRuntimeStage:
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
class CausalBetaFrontierRuntimeReport:
    run_id: str
    fixture: CausalBetaFrontierFixture
    adapters: CausalBetaFrontierAdapterRegistry
    evaluation: CausalBetaFrontierEvaluation
    contracts: CausalBetaFrontierContractReport
    schema: CausalBetaFrontierSchemaReport
    metrics: CausalBetaFrontierMetrics
    lineage: CausalBetaFrontierLineage
    provenance: CausalBetaFrontierProvenanceGraph
    depth: CausalBetaFrontierDepthAudit
    policy: CausalBetaFrontierPolicy
    decisions: tuple[Any, ...]
    reconciliation: CausalBetaFrontierReconciliation
    review: CausalBetaFrontierReviewQueue
    scenario: CausalBetaFrontierScenarioMatrix
    validation: CausalBetaFrontierValidationMatrix
    gate: CausalBetaFrontierQualityGate
    bundle: CausalBetaFrontierReleaseBundle
    release: CausalBetaFrontierReleaseManifest
    artifacts: CausalBetaFrontierArtifactInventory
    integrity: CausalBetaFrontierIntegrityReport
    operational: CausalBetaFrontierOperationalMatrix
    boundary: CausalBetaFrontierClaimBoundaryReport
    replay: CausalBetaFrontierReplayReceipt
    review_view: CausalBetaFrontierReviewView
    exports: CausalBetaFrontierExportInventory
    assurance: CausalBetaFrontierAssurance
    runbook: CausalBetaFrontierRunbook
    stages: tuple[CausalBetaFrontierRuntimeStage, ...]
    observability: Any
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
        value = {"run_id": self.run_id, "fixture": self.fixture.to_dict(), "adapters": self.adapters.to_dict(), "evaluation": self.evaluation.to_dict(), "contracts": self.contracts.to_dict(), "schema": self.schema.to_dict(), "metrics": self.metrics.to_dict(), "lineage": self.lineage.to_dict(), "provenance": self.provenance.to_dict(), "depth": self.depth.to_dict(), "policy": self.policy.to_dict(), "decisions": [jsonable(item) for item in self.decisions], "reconciliation": self.reconciliation.to_dict(), "review": self.review.to_dict(), "scenario": self.scenario.to_dict(), "validation": self.validation.to_dict(), "gate": self.gate.to_dict(), "bundle": self.bundle.to_dict(), "release": self.release.to_dict(), "artifacts": self.artifacts.to_dict(), "integrity": self.integrity.to_dict(), "operational": self.operational.to_dict(), "boundary": self.boundary.to_dict(), "replay": self.replay.to_dict(), "review_view": self.review_view.to_dict(), "exports": self.exports.to_dict(), "assurance": self.assurance.to_dict(), "runbook": self.runbook.to_dict(), "stages": [item.to_dict() for item in self.stages], "observability": self.observability.to_dict(), "stage_ids": self.stage_ids, "stage_count": self.stage_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_causal_beta_frontier_runtime(fixture: CausalBetaFrontierFixture | None = None, *, run_id: str = "causal-beta-frontier-runtime") -> CausalBetaFrontierRuntimeReport:
    value = fixture or default_causal_beta_frontier_fixture()
    events = []
    stages = []

    def stage(stage_id: str, sequence: int, fn: Any, detail: str) -> Any:
        result, event = record_causal_beta_frontier_event(run_id, sequence, stage_id, fn, detail)
        events.append(event)
        stages.append(CausalBetaFrontierRuntimeStage(stage_id, sequence, event.state, event.output_address, detail))
        if result is None:
            raise RuntimeError(event.detail)
        return result

    audit = stage("data-audit", 1, lambda: audit_causal_beta_frontier_data(value), "validate public beta fixture")
    adapters = stage("adapters", 2, build_causal_beta_frontier_adapters, "bind four beta primitives")
    evaluation = stage("fixture-replay", 3, lambda: evaluate_causal_beta_frontier_fixture(value), "replay mediator and allele controls")
    contracts = stage("contracts", 4, build_causal_beta_frontier_contracts, "load capability contracts")
    schema = stage("schema", 5, lambda: validate_causal_beta_frontier_schema(value, evaluation), "validate record envelope")
    metrics = stage("metrics", 6, lambda: build_causal_beta_frontier_metrics(evaluation, value), "calculate operation metrics")
    lineage = stage("lineage", 7, lambda: build_causal_beta_frontier_lineage(value, evaluation), "build source-to-result lineage")
    provenance = stage("provenance", 8, lambda: build_causal_beta_frontier_provenance(value, evaluation), "build provenance graph")
    integrity = stage("integrity", 9, lambda: evaluate_causal_beta_frontier_integrity(value, evaluation, lineage, provenance), "verify addresses and graph integrity")
    depth = stage("depth-audit", 10, lambda: audit_causal_beta_frontier_depth(value, evaluation, adapters, contracts, schema, metrics, lineage, provenance), "audit implementation depth")
    policy = stage("policy", 11, default_causal_beta_frontier_policy, "apply bounded dispositions")
    decisions = stage("decisions", 12, lambda: policy.decide(evaluation), "produce row decisions")
    reconciliation = stage("reconciliation", 13, lambda: reconcile_causal_beta_frontier(value, evaluation, decisions, policy), "reconcile expected and observed floors")
    review = stage("review-queue", 14, lambda: build_causal_beta_frontier_review_queue(evaluation, policy), "project review queue")
    scenario = stage("scenario-matrix", 15, lambda: build_causal_beta_frontier_scenario_matrix(value, evaluation), "build scenario matrix")
    validation = stage("validation-matrix", 16, lambda: build_causal_beta_frontier_validation_matrix(value, evaluation), "build capability validation matrix")
    gate = stage("quality-gate", 17, lambda: evaluate_causal_beta_frontier_quality(value, evaluation, contracts, schema, metrics, lineage, reconciliation, depth, review, decisions), "run quality gate")
    bundle = stage("release-bundle", 18, lambda: assemble_causal_beta_frontier_bundle(value, evaluation, metrics, contracts, schema, lineage, provenance, depth, reconciliation, policy, review, gate, scenario, validation, bundle_id=run_id), "assemble release bundle")
    release = stage("release-manifest", 19, lambda: build_causal_beta_frontier_release_manifest(bundle, gate, depth, review), "build release manifest")
    artifacts = stage("artifact-inventory", 20, lambda: build_causal_beta_frontier_artifact_inventory(value, evaluation, bundle, release), "enumerate release artifacts")
    replay = stage("deterministic-replay", 21, lambda: replay_causal_beta_frontier(value, replay_id=run_id + ":replay"), "replay fixture twice")
    operational = stage("operational-matrix", 22, lambda: build_causal_beta_frontier_operational_matrix(value, evaluation, decisions, review, bundle), "project bounded operational actions")
    boundary = stage("claim-boundary", 23, lambda: build_causal_beta_frontier_claim_boundary(bundle, operational), "enforce allowed and excluded uses")
    review_view = stage("review-view", 24, lambda: build_causal_beta_frontier_review_view(value, evaluation, decisions, reconciliation, review), "build stable review table")
    exports = stage("exports", 25, lambda: build_causal_beta_frontier_exports(value, evaluation, metrics, review_view, bundle, release, artifacts), "assemble canonical exports")
    report_proxy = type("CausalBetaFrontierRuntimeProxy", (), {"accepted": bool(audit.accepted and evaluation.accepted and gate.accepted and bundle.publishable and release.accepted and artifacts.accepted), "fixture": value, "bundle": bundle})()
    assurance = stage("assurance", 26, lambda: build_causal_beta_frontier_assurance(report_proxy, replay, integrity, operational, boundary, exports, release), "assemble assurance statement")
    runbook = stage("runbook", 27, lambda: build_causal_beta_frontier_runbook(run_id, value.fixture_id, 27, release, bundle, boundary, assurance), "publish executable release runbook")
    observability = build_causal_beta_frontier_observability(run_id, tuple(events))
    accepted = bool(report_proxy.accepted and observability.accepted and integrity.accepted and operational.accepted and boundary.accepted and replay.deterministic and exports.accepted and assurance.accepted and runbook.accepted)
    return CausalBetaFrontierRuntimeReport(run_id, value, adapters, evaluation, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, scenario, validation, gate, bundle, release, artifacts, integrity, operational, boundary, replay, review_view, exports, assurance, runbook, tuple(stages), observability, accepted)


__all__ = ["CausalBetaFrontierRuntimeReport", "CausalBetaFrontierRuntimeStage", "run_causal_beta_frontier_runtime"]
