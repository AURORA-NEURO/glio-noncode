"""Ordered runtime for the Domain 12 C01-C04 release rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_adapters import CohortFoundationAdapterRegistry, default_cohort_foundation_frontier_adapters
from .cohort_foundation_frontier_artifacts import CohortFoundationArtifactInventory, build_cohort_foundation_frontier_artifact_inventory
from .cohort_foundation_frontier_assurance import CohortFoundationAssurance, build_cohort_foundation_frontier_assurance
from .cohort_foundation_frontier_accessibility import CohortFoundationAccessibilityReport, build_cohort_foundation_frontier_accessibility_report
from .cohort_foundation_frontier_bundle import CohortFoundationReleaseBundle, assemble_cohort_foundation_frontier_bundle
from .cohort_foundation_frontier_claim_boundary import CohortFoundationClaimBoundary, build_cohort_foundation_frontier_claim_boundary
from .cohort_foundation_frontier_checks import CohortFoundationInvariantReport, run_cohort_foundation_frontier_invariants
from .cohort_foundation_frontier_control_coverage import CohortFoundationControlCoverage, build_cohort_foundation_frontier_control_coverage
from .cohort_foundation_frontier_failure_injection import CohortFoundationFailureInjectionReport, run_cohort_foundation_frontier_failure_injections
from .cohort_foundation_frontier_contracts import CohortFoundationContractRegistry, default_cohort_foundation_frontier_contracts
from .cohort_foundation_frontier_depth import CohortFoundationDepthAudit, audit_cohort_foundation_frontier_depth
from .cohort_foundation_frontier_diagnostics import CohortFoundationDiagnosticReport, build_cohort_foundation_frontier_diagnostics
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation, evaluate_cohort_foundation_frontier_fixture
from .cohort_foundation_frontier_integrity import CohortFoundationIntegrityReport, evaluate_cohort_foundation_frontier_integrity
from .cohort_foundation_frontier_lineage import CohortFoundationLineageGraph, build_cohort_foundation_frontier_lineage
from .cohort_foundation_frontier_metrics import CohortFoundationMetrics, measure_cohort_foundation_frontier
from .cohort_foundation_frontier_observability import CohortFoundationObservabilityReport, observe_cohort_foundation_frontier
from .cohort_foundation_frontier_policy import CohortFoundationPolicy, materialize_cohort_foundation_frontier_policy
from .cohort_foundation_frontier_package import CohortFoundationPackageManifest, build_cohort_foundation_frontier_package_manifest
from .cohort_foundation_frontier_performance import CohortFoundationPerformanceReport, build_cohort_foundation_frontier_performance_report
from .cohort_foundation_frontier_provenance import CohortFoundationProvenanceGraph, build_cohort_foundation_frontier_provenance
from .cohort_foundation_frontier_public_data import CohortFoundationFixture, CohortFoundationDataAudit, audit_cohort_foundation_frontier_data, default_cohort_foundation_frontier_fixture
from .cohort_foundation_frontier_quality_gate import CohortFoundationQualityGate, evaluate_cohort_foundation_frontier_quality
from .cohort_foundation_frontier_reconciliation import CohortFoundationReconciliation, reconcile_cohort_foundation_frontier
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest, build_cohort_foundation_frontier_release_manifest
from .cohort_foundation_frontier_recovery import CohortFoundationRecoveryPlan, build_cohort_foundation_frontier_recovery_plan
from .cohort_foundation_frontier_replay import CohortFoundationReplayReceipt, replay_cohort_foundation_frontier
from .cohort_foundation_frontier_review import CohortFoundationReviewQueue, build_cohort_foundation_frontier_review_queue
from .cohort_foundation_frontier_schema import CohortFoundationSchemaReport, default_cohort_foundation_frontier_schema
from .cohort_foundation_frontier_schema_migrations import CohortFoundationSchemaMigrationReport, build_cohort_foundation_frontier_schema_migration_report
from .cohort_foundation_frontier_source_registry import CohortFoundationSourceRegistry, build_cohort_foundation_frontier_source_registry
from .cohort_foundation_frontier_thresholds import CohortFoundationThresholdReport, build_cohort_foundation_frontier_threshold_report
from .cohort_foundation_frontier_traces import CohortFoundationTraceLedger, build_cohort_foundation_frontier_trace_ledger
from .cohort_foundation_frontier_operational import CohortFoundationOperationalMatrix, build_cohort_foundation_frontier_operational_matrix
from .cohort_foundation_frontier_query import CohortFoundationQueryResult, query_cohort_foundation_frontier
from .cohort_foundation_frontier_runbook import CohortFoundationRunbook, build_cohort_foundation_frontier_runbook
from .cohort_foundation_frontier_scenario_matrix import CohortFoundationScenarioMatrix, build_cohort_foundation_frontier_scenario_matrix
from .cohort_foundation_frontier_validation_matrix import CohortFoundationValidationMatrix, build_cohort_foundation_frontier_validation_matrix
from .cohort_foundation_frontier_views import CohortFoundationReviewView, build_cohort_foundation_frontier_review_view


@dataclass(frozen=True, slots=True)
class CohortFoundationRuntimeStage:
    ordinal: int
    stage_id: str
    accepted: bool
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationRuntimeReport:
    run_id: str
    fixture: CohortFoundationFixture
    data_audit: CohortFoundationDataAudit
    adapters: CohortFoundationAdapterRegistry
    contracts: CohortFoundationContractRegistry
    schema: CohortFoundationSchemaReport
    evaluation: CohortFoundationEvaluation
    metrics: CohortFoundationMetrics
    lineage: CohortFoundationLineageGraph
    provenance: CohortFoundationProvenanceGraph
    policy: CohortFoundationPolicy
    reconciliation: CohortFoundationReconciliation
    review: CohortFoundationReviewQueue
    quality: CohortFoundationQualityGate
    replay: CohortFoundationReplayReceipt
    bundle: CohortFoundationReleaseBundle
    release: CohortFoundationReleaseManifest
    artifacts: CohortFoundationArtifactInventory
    diagnostics: CohortFoundationDiagnosticReport
    review_view: CohortFoundationReviewView
    depth: CohortFoundationDepthAudit
    scenarios: CohortFoundationScenarioMatrix
    validation: CohortFoundationValidationMatrix
    operational: CohortFoundationOperationalMatrix
    claim_boundary: CohortFoundationClaimBoundary
    assurance: CohortFoundationAssurance
    runbook: CohortFoundationRunbook
    query: CohortFoundationQueryResult
    source_registry: CohortFoundationSourceRegistry
    integrity: CohortFoundationIntegrityReport
    control_coverage: CohortFoundationControlCoverage
    traces: CohortFoundationTraceLedger
    invariants: CohortFoundationInvariantReport
    thresholds: CohortFoundationThresholdReport
    observability: CohortFoundationObservabilityReport
    accessibility: CohortFoundationAccessibilityReport
    performance: CohortFoundationPerformanceReport
    schema_migrations: CohortFoundationSchemaMigrationReport
    failure_injections: CohortFoundationFailureInjectionReport
    recovery: CohortFoundationRecoveryPlan
    package: CohortFoundationPackageManifest
    stages: tuple[CohortFoundationRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_cohort_foundation_frontier_runtime(fixture: CohortFoundationFixture | None = None, *, run_id: str = "cohort-foundation-frontier-runtime") -> CohortFoundationRuntimeReport:
    value = fixture or default_cohort_foundation_frontier_fixture()
    stages: list[CohortFoundationRuntimeStage] = []

    def stage(stage_id: str, output: Any, accepted: bool, detail: str) -> None:
        stages.append(CohortFoundationRuntimeStage(len(stages) + 1, stage_id, accepted, content_hash(output), detail))

    data_audit = audit_cohort_foundation_frontier_data(value)
    stage("data-audit", data_audit, data_audit.accepted, "source and boundary audit")
    source_registry = build_cohort_foundation_frontier_source_registry(value)
    stage("source-registry", source_registry, source_registry.closed, "declared public source registry")
    adapters = default_cohort_foundation_frontier_adapters()
    stage("adapters", adapters, True, "four strict input adapters")
    contracts = default_cohort_foundation_frontier_contracts()
    stage("contracts", contracts, True, "four operation contracts")
    schema = default_cohort_foundation_frontier_schema()
    stage("schema", schema, schema.accepted, "field schema closure")
    schema_migrations = build_cohort_foundation_frontier_schema_migration_report()
    stage("schema-migrations", schema_migrations, schema_migrations.accepted, "schema evolution receipts")
    evaluation = evaluate_cohort_foundation_frontier_fixture(value)
    stage("fixture-evaluation", evaluation, evaluation.accepted, "positive and control replay")
    integrity = evaluate_cohort_foundation_frontier_integrity(value, evaluation)
    stage("integrity", integrity, integrity.accepted, "address and duplicate checks")
    metrics = measure_cohort_foundation_frontier(evaluation)
    stage("metrics", metrics, metrics.execution_count == len(value.records), "operation coverage metrics")
    performance = build_cohort_foundation_frontier_performance_report(evaluation)
    stage("performance-budget", performance, performance.accepted, "bounded resource budgets")
    control_coverage = build_cohort_foundation_frontier_control_coverage(evaluation)
    stage("control-coverage", control_coverage, control_coverage.accepted, "state-class coverage")
    lineage = build_cohort_foundation_frontier_lineage(value, evaluation)
    stage("lineage", lineage, len(lineage.edges) >= len(value.records) * 2, "source and execution lineage")
    provenance = build_cohort_foundation_frontier_provenance(value, evaluation)
    stage("provenance", provenance, provenance.closed, "source receipt closure")
    policy = materialize_cohort_foundation_frontier_policy(evaluation, contracts)
    stage("policy", policy, len(policy.decisions) == len(evaluation.executions), "state-aware publication policy")
    traces = build_cohort_foundation_frontier_trace_ledger(value, evaluation, policy)
    stage("decision-traces", traces, traces.accepted, "source-execution-policy traces")
    reconciliation = reconcile_cohort_foundation_frontier(value, evaluation, policy)
    stage("reconciliation", reconciliation, reconciliation.reconciled, "expected-state reconciliation")
    invariants = run_cohort_foundation_frontier_invariants(value, evaluation, policy, reconciliation)
    stage("invariants", invariants, invariants.accepted, "blocking invariant checks")
    failure_injections = run_cohort_foundation_frontier_failure_injections(value)
    stage("failure-injections", failure_injections, failure_injections.accepted, "controlled failure boundaries")
    review = build_cohort_foundation_frontier_review_queue(evaluation, policy)
    stage("review-queue", review, review.accepted, "incomplete and foreign paths")
    quality = evaluate_cohort_foundation_frontier_quality(value, evaluation, contracts, schema, lineage, reconciliation)
    stage("quality-gate", quality, quality.accepted, "blocking release checks")
    replay = replay_cohort_foundation_frontier(value, replay_id=run_id + "-replay")
    stage("replay", replay, replay.deterministic, "deterministic evaluation replay")
    bundle = assemble_cohort_foundation_frontier_bundle(value, evaluation, metrics, lineage, provenance, policy, reconciliation, quality, review)
    stage("bundle", bundle, bundle.accepted, "content-addressed release bundle")
    release = build_cohort_foundation_frontier_release_manifest(bundle, quality, replay)
    stage("release", release, release.ready, "release manifest")
    artifacts = build_cohort_foundation_frontier_artifact_inventory(bundle, release)
    stage("artifacts", artifacts, artifacts.complete, "artifact inventory")
    package = build_cohort_foundation_frontier_package_manifest(artifacts, release)
    stage("package", package, package.ready, "file-level release package")
    diagnostics = build_cohort_foundation_frontier_diagnostics(value, evaluation, metrics, policy, reconciliation)
    stage("diagnostics", diagnostics, diagnostics.accepted, "cross-plane diagnostics")
    review_view = build_cohort_foundation_frontier_review_view(evaluation, policy, value.context_key)
    stage("review-view", review_view, bool(review_view.rows), "review projection")
    accessibility = build_cohort_foundation_frontier_accessibility_report(review_view)
    stage("accessibility", accessibility, accessibility.accepted, "review field visibility")
    depth = audit_cohort_foundation_frontier_depth(value, evaluation, metrics, lineage, quality, release, artifacts)
    stage("depth-audit", depth, depth.accepted, "quantitative depth thresholds")
    scenarios = build_cohort_foundation_frontier_scenario_matrix(evaluation)
    stage("scenario-matrix", scenarios, scenarios.accepted, "state and context probes")
    validation = build_cohort_foundation_frontier_validation_matrix(contracts, evaluation)
    stage("validation-matrix", validation, validation.accepted, "contract-to-evidence matrix")
    operational = build_cohort_foundation_frontier_operational_matrix(policy)
    stage("operational-matrix", operational, operational.accepted, "consumer disposition matrix")
    claim_boundary = build_cohort_foundation_frontier_claim_boundary(contracts)
    stage("claim-boundary", claim_boundary, claim_boundary.accepted, "allowed and prohibited claims")
    thresholds = build_cohort_foundation_frontier_threshold_report()
    stage("thresholds", thresholds, thresholds.accepted, "parameter boundary probes")
    diagnostics = build_cohort_foundation_frontier_diagnostics(value, evaluation, metrics, policy, reconciliation)
    assurance = build_cohort_foundation_frontier_assurance(release, depth, replay, diagnostics, len(review.items), sum(item.disposition.value == "quarantine" for item in policy.decisions))
    stage("assurance", assurance, assurance.accepted, "cross-plane assurance")
    accepted = all(item.accepted for item in stages)
    runbook = build_cohort_foundation_frontier_runbook(type("RuntimeSnapshot", (), {"stages": tuple(stages), "accepted": accepted})())
    stage("runbook", runbook, runbook.executable, "ordered operator runbook")
    query = query_cohort_foundation_frontier(review_view, operation=None, limit=5)
    stage("query", query, query.total >= len(query.rows), "deterministic review query")
    observability = observe_cohort_foundation_frontier(value.fixture_id, stages, emitted_at="2026-08-22T00:00:00+00:00")
    stage("observability", observability, observability.accepted, "structured runtime events")
    recovery = build_cohort_foundation_frontier_recovery_plan(policy, quality, release)
    stage("recovery", recovery, recovery.executable, "review and release recovery plan")
    accepted = all(item.accepted for item in stages)
    body = {"run_id": run_id, "fixture_id": value.fixture_id, "stages": stages, "release": release.content_address, "depth": depth.content_address}
    return CohortFoundationRuntimeReport(run_id, value, data_audit, adapters, contracts, schema, evaluation, metrics, lineage, provenance, policy, reconciliation, review, quality, replay, bundle, release, artifacts, diagnostics, review_view, depth, scenarios, validation, operational, claim_boundary, assurance, runbook, query, source_registry, integrity, control_coverage, traces, invariants, thresholds, observability, accessibility, performance, schema_migrations, failure_injections, recovery, package, tuple(stages), accepted, content_hash(body))


__all__ = ["CohortFoundationRuntimeReport", "CohortFoundationRuntimeStage", "run_cohort_foundation_frontier_runtime"]
