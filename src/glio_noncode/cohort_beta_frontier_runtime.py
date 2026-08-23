"""Ordered runtime for Domain 12 C05-C08 release rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_accessibility import CohortBetaFrontierAccessibilityReport, build_cohort_beta_frontier_accessibility_report
from .cohort_beta_frontier_adapters import CohortBetaFrontierAdapterRegistry, default_cohort_beta_frontier_adapters
from .cohort_beta_frontier_assurance import CohortBetaFrontierAssurance, build_cohort_beta_frontier_assurance
from .cohort_beta_frontier_bundle import CohortBetaFrontierReleaseBundle, assemble_cohort_beta_frontier_bundle
from .cohort_beta_frontier_claim_boundary import CohortBetaFrontierClaimBoundary, build_cohort_beta_frontier_claim_boundary
from .cohort_beta_frontier_claim_evidence import CohortBetaFrontierClaimEvidenceLedger, build_cohort_beta_frontier_claim_evidence_ledger
from .cohort_beta_frontier_checks import CohortBetaFrontierInvariantReport, run_cohort_beta_frontier_invariants
from .cohort_beta_frontier_contracts import CohortBetaFrontierContractRegistry, default_cohort_beta_frontier_contracts
from .cohort_beta_frontier_control_coverage import CohortBetaFrontierControlCoverage, build_cohort_beta_frontier_control_coverage
from .cohort_beta_frontier_dataset_manifest import CohortBetaFrontierDatasetManifest, build_cohort_beta_frontier_dataset_manifest
from .cohort_beta_frontier_depth import CohortBetaFrontierDepthAudit, audit_cohort_beta_frontier_depth
from .cohort_beta_frontier_diagnostics import CohortBetaFrontierDiagnosticReport, build_cohort_beta_frontier_diagnostics
from .cohort_beta_frontier_failure_injection import CohortBetaFrontierFailureInjectionReport, run_cohort_beta_frontier_failure_injections
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation, evaluate_cohort_beta_frontier_fixture
from .cohort_beta_frontier_integrity import CohortBetaFrontierIntegrityReport, evaluate_cohort_beta_frontier_integrity
from .cohort_beta_frontier_lineage import CohortBetaFrontierLineage, build_cohort_beta_frontier_lineage
from .cohort_beta_frontier_metrics import CohortBetaFrontierMetrics, measure_cohort_beta_frontier
from .cohort_beta_frontier_observability import CohortBetaFrontierObservabilityReport, observe_cohort_beta_frontier
from .cohort_beta_frontier_operational import CohortBetaFrontierOperationalMatrix, build_cohort_beta_frontier_operational_matrix
from .cohort_beta_frontier_package import CohortBetaFrontierPackageManifest, build_cohort_beta_frontier_package_manifest
from .cohort_beta_frontier_performance import CohortBetaFrontierPerformanceReport, build_cohort_beta_frontier_performance_report
from .cohort_beta_frontier_policy import CohortBetaFrontierPolicy, materialize_cohort_beta_frontier_policy
from .cohort_beta_frontier_provenance import CohortBetaFrontierProvenanceGraph, build_cohort_beta_frontier_provenance
from .cohort_beta_frontier_public_data import CohortBetaFrontierDataAudit, CohortBetaFrontierFixture, audit_cohort_beta_frontier_data, default_cohort_beta_frontier_fixture
from .cohort_beta_frontier_quality_gate import CohortBetaFrontierQualityGate, evaluate_cohort_beta_frontier_quality
from .cohort_beta_frontier_reconciliation import CohortBetaFrontierReconciliation, reconcile_cohort_beta_frontier
from .cohort_beta_frontier_recovery import CohortBetaFrontierRecoveryPlan, build_cohort_beta_frontier_recovery_plan
from .cohort_beta_frontier_release import CohortBetaFrontierReleaseManifest, build_cohort_beta_frontier_release_manifest
from .cohort_beta_frontier_replay import CohortBetaFrontierReplayReceipt, replay_cohort_beta_frontier
from .cohort_beta_frontier_review import CohortBetaFrontierReviewQueue, build_cohort_beta_frontier_review_queue
from .cohort_beta_frontier_runbook import CohortBetaFrontierRunbook, build_cohort_beta_frontier_runbook
from .cohort_beta_frontier_scenario_matrix import CohortBetaFrontierScenarioMatrix, build_cohort_beta_frontier_scenario_matrix
from .cohort_beta_frontier_schema import CohortBetaFrontierSchemaReport, default_cohort_beta_frontier_schema
from .cohort_beta_frontier_schema_migrations import CohortBetaFrontierSchemaMigrationReport, build_cohort_beta_frontier_schema_migration_report
from .cohort_beta_frontier_source_registry import CohortBetaFrontierSourceRegistry, build_cohort_beta_frontier_source_registry
from .cohort_beta_frontier_thresholds import CohortBetaFrontierThresholdReport, build_cohort_beta_frontier_threshold_report
from .cohort_beta_frontier_traces import CohortBetaFrontierTraceLedger, build_cohort_beta_frontier_trace_ledger
from .cohort_beta_frontier_validation_matrix import CohortBetaFrontierValidationMatrix, build_cohort_beta_frontier_validation_matrix
from .cohort_beta_frontier_views import CohortBetaFrontierReviewView, build_cohort_beta_frontier_review_view
from .cohort_beta_frontier_runtime_types import CohortBetaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierRuntimeReport:
    run_id: str
    fixture: CohortBetaFrontierFixture
    data_audit: CohortBetaFrontierDataAudit
    adapters: CohortBetaFrontierAdapterRegistry
    contracts: CohortBetaFrontierContractRegistry
    schema: CohortBetaFrontierSchemaReport
    evaluation: CohortBetaFrontierEvaluation
    metrics: CohortBetaFrontierMetrics
    lineage: CohortBetaFrontierLineage
    provenance: CohortBetaFrontierProvenanceGraph
    policy: CohortBetaFrontierPolicy
    reconciliation: CohortBetaFrontierReconciliation
    quality: CohortBetaFrontierQualityGate
    replay: CohortBetaFrontierReplayReceipt
    bundle: CohortBetaFrontierReleaseBundle
    release: CohortBetaFrontierReleaseManifest
    review: CohortBetaFrontierReviewQueue
    scenarios: CohortBetaFrontierScenarioMatrix
    validation: CohortBetaFrontierValidationMatrix
    operational: CohortBetaFrontierOperationalMatrix
    claim_boundary: CohortBetaFrontierClaimBoundary
    assurance: CohortBetaFrontierAssurance
    claim_evidence: CohortBetaFrontierClaimEvidenceLedger
    source_registry: CohortBetaFrontierSourceRegistry
    integrity: CohortBetaFrontierIntegrityReport
    control_coverage: CohortBetaFrontierControlCoverage
    traces: CohortBetaFrontierTraceLedger
    thresholds: CohortBetaFrontierThresholdReport
    observability: CohortBetaFrontierObservabilityReport
    accessibility: CohortBetaFrontierAccessibilityReport
    performance: CohortBetaFrontierPerformanceReport
    migrations: CohortBetaFrontierSchemaMigrationReport
    failure_injections: CohortBetaFrontierFailureInjectionReport
    recovery: CohortBetaFrontierRecoveryPlan
    dataset_manifest: CohortBetaFrontierDatasetManifest
    invariants: CohortBetaFrontierInvariantReport
    runbook: CohortBetaFrontierRunbook
    stages: tuple[CohortBetaFrontierRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_cohort_beta_frontier_runtime(fixture: CohortBetaFrontierFixture | None = None, *, run_id: str = "cohort-beta-frontier-runtime") -> CohortBetaFrontierRuntimeReport:
    value = fixture or default_cohort_beta_frontier_fixture()
    stages: list[CohortBetaFrontierRuntimeStage] = []

    def stage(stage_id: str, output: Any, accepted: bool, detail: str) -> None:
        serialized = output.to_dict() if hasattr(output, "to_dict") else output
        stages.append(CohortBetaFrontierRuntimeStage(len(stages) + 1, stage_id, accepted, content_hash(jsonable(serialized)), detail))

    data_audit = audit_cohort_beta_frontier_data(value); stage("data-audit", data_audit, data_audit.accepted, "public source and boundary audit")
    source_registry = build_cohort_beta_frontier_source_registry(value); stage("source-registry", source_registry, source_registry.closed, "public source closure")
    adapters = default_cohort_beta_frontier_adapters(); stage("adapters", adapters, len(adapters.specs) == 4, "strict operation adapters")
    contracts = default_cohort_beta_frontier_contracts(); stage("contracts", contracts, len(contracts.contracts) == 4, "operation contracts")
    schema = default_cohort_beta_frontier_schema(); stage("schema", schema, schema.accepted, "field schema closure")
    migrations = build_cohort_beta_frontier_schema_migration_report(); stage("schema-migrations", migrations, migrations.accepted, "forward schema receipts")
    evaluation = evaluate_cohort_beta_frontier_fixture(value); stage("fixture-evaluation", evaluation, evaluation.accepted, "positive and control paths")
    integrity = evaluate_cohort_beta_frontier_integrity(value, evaluation); stage("integrity", integrity, integrity.accepted, "address and duplicate checks")
    metrics = measure_cohort_beta_frontier(evaluation); stage("metrics", metrics, metrics.accepted_rows == 16, "coverage metrics")
    performance = build_cohort_beta_frontier_performance_report(evaluation); stage("performance", performance, performance.accepted, "bounded resource receipt")
    lineage = build_cohort_beta_frontier_lineage(value, evaluation); stage("lineage", lineage, lineage.closed, "source-to-result lineage")
    provenance = build_cohort_beta_frontier_provenance(value, evaluation); stage("provenance", provenance, provenance.closed, "public source provenance")
    policy = materialize_cohort_beta_frontier_policy(evaluation, contracts); stage("policy", policy, len(policy.decisions) == 16, "state-aware policy")
    traces = build_cohort_beta_frontier_trace_ledger(evaluation, policy, reconcile_cohort_beta_frontier(value, evaluation, policy)); stage("traces", traces, traces.accepted, "decision traces")
    reconciliation = reconcile_cohort_beta_frontier(value, evaluation, policy); stage("reconciliation", reconciliation, reconciliation.reconciled, "expected-state reconciliation")
    invariants = run_cohort_beta_frontier_invariants(value, evaluation, policy, reconciliation); stage("invariants", invariants, invariants.accepted, "blocking invariants")
    failure_injections = run_cohort_beta_frontier_failure_injections(value); stage("failure-injections", failure_injections, failure_injections.accepted, "controlled negative probes")
    review = build_cohort_beta_frontier_review_queue(evaluation, policy); stage("review", review, review.accepted, "partial and quarantined paths")
    quality = evaluate_cohort_beta_frontier_quality(value, evaluation, contracts, schema, lineage, reconciliation); stage("quality", quality, quality.accepted, "release quality gate")
    replay = replay_cohort_beta_frontier(value, replay_id=run_id + "-replay"); stage("replay", replay, replay.deterministic, "deterministic replay")
    bundle = assemble_cohort_beta_frontier_bundle(value, evaluation, metrics, lineage, provenance, policy, reconciliation, quality, review); stage("bundle", bundle, bundle.accepted, "content-addressed bundle")
    release = build_cohort_beta_frontier_release_manifest(bundle, quality, replay); stage("release", release, release.ready, "release manifest")
    scenarios = build_cohort_beta_frontier_scenario_matrix(evaluation); stage("scenarios", scenarios, scenarios.accepted, "scenario matrix")
    validation = build_cohort_beta_frontier_validation_matrix(contracts, evaluation); stage("validation", validation, validation.accepted, "contract validation")
    operational = build_cohort_beta_frontier_operational_matrix(policy); stage("operational", operational, operational.accepted, "consumer disposition")
    claim_boundary = build_cohort_beta_frontier_claim_boundary(contracts); stage("claim-boundary", claim_boundary, claim_boundary.accepted, "claim ceiling")
    claim_evidence = build_cohort_beta_frontier_claim_evidence_ledger(value, evaluation, claim_boundary); stage("claim-evidence", claim_evidence, claim_evidence.accepted, "claim support ledger")
    control_coverage = build_cohort_beta_frontier_control_coverage(evaluation); stage("control-coverage", control_coverage, control_coverage.accepted, "control class coverage")
    thresholds = build_cohort_beta_frontier_threshold_report(); stage("thresholds", thresholds, thresholds.accepted, "threshold boundaries")
    accessibility = build_cohort_beta_frontier_accessibility_report(build_cohort_beta_frontier_review_view(evaluation, policy, value.context_key)); stage("accessibility", accessibility, accessibility.accepted, "review field visibility")
    dataset_manifest = build_cohort_beta_frontier_dataset_manifest(value); stage("dataset-manifest", dataset_manifest, dataset_manifest.closed, "dataset source separation")
    diagnostics = build_cohort_beta_frontier_diagnostics(evaluation, metrics, policy, reconciliation)
    assurance = build_cohort_beta_frontier_assurance(release, audit_cohort_beta_frontier_depth(value, evaluation, metrics, lineage, quality), replay, diagnostics, review.open_count, policy.quarantine_count); stage("assurance", assurance, assurance.accepted, "cross-plane assurance")
    depth = audit_cohort_beta_frontier_depth(value, evaluation, metrics, lineage, quality); stage("depth", depth, depth.accepted, "depth thresholds")
    recovery = build_cohort_beta_frontier_recovery_plan(policy, quality, release); stage("recovery", recovery, recovery.executable, "recovery actions")
    runbook = build_cohort_beta_frontier_runbook(); stage("runbook", runbook, runbook.executable, "operator runbook")
    accepted = all(item.accepted for item in stages)
    body = {"run_id": run_id, "fixture": value.fixture_id, "stages": stages, "release": release.content_address, "accepted": accepted}
    observability = observe_cohort_beta_frontier(value.fixture_id, stages, emitted_at="2026-08-22T00:00:00+00:00"); stage("observability", observability, observability.accepted, "structured runtime events")
    accepted = all(item.accepted for item in stages)
    return CohortBetaFrontierRuntimeReport(run_id, value, data_audit, adapters, contracts, schema, evaluation, metrics, lineage, provenance, policy, reconciliation, quality, replay, bundle, release, review, scenarios, validation, operational, claim_boundary, assurance, claim_evidence, source_registry, integrity, control_coverage, traces, thresholds, observability, accessibility, performance, migrations, failure_injections, recovery, dataset_manifest, invariants, runbook, tuple(stages), accepted, content_hash(body, prefix="runtime"))


__all__ = ["CohortBetaFrontierRuntimeReport", "CohortBetaFrontierRuntimeStage", "run_cohort_beta_frontier_runtime"]
