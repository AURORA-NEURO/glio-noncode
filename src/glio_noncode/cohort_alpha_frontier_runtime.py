"""End-to-end deterministic runtime for the C09-C12 depth tranche."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Callable

from .cohort_alpha_frontier_adapters import CohortAlphaFrontierAdapterRegistry, default_cohort_alpha_frontier_adapters
from .cohort_alpha_frontier_api_contract import CohortAlphaFrontierApiContract, default_cohort_alpha_frontier_api_contract
from .cohort_alpha_frontier_assurance import CohortAlphaFrontierAssuranceReport, evaluate_cohort_alpha_frontier_assurance
from .cohort_alpha_frontier_audit_log import CohortAlphaFrontierAuditLog, build_cohort_alpha_frontier_audit_log
from .cohort_alpha_frontier_accessibility import CohortAlphaFrontierAccessibilityReport, build_cohort_alpha_frontier_accessibility
from .cohort_alpha_frontier_calibration import CohortAlphaFrontierCalibrationReport, build_cohort_alpha_frontier_calibration
from .cohort_alpha_frontier_change_control import CohortAlphaFrontierChangeControl, build_cohort_alpha_frontier_change_control
from .cohort_alpha_frontier_claim_boundary import CohortAlphaFrontierClaimBoundary, build_cohort_alpha_frontier_claim_boundary
from .cohort_alpha_frontier_claim_evidence import CohortAlphaFrontierClaimEvidenceReport, build_cohort_alpha_frontier_claim_evidence
from .cohort_alpha_frontier_claim_dictionary import CohortAlphaFrontierClaimDictionary, build_cohort_alpha_frontier_claim_dictionary
from .cohort_alpha_frontier_compatibility import CohortAlphaFrontierCompatibilityReport, build_cohort_alpha_frontier_compatibility
from .cohort_alpha_frontier_control_coverage import CohortAlphaFrontierControlCoverage, build_cohort_alpha_frontier_control_coverage
from .cohort_alpha_frontier_contracts import CohortAlphaFrontierContractRegistry, default_cohort_alpha_frontier_contracts
from .cohort_alpha_frontier_data_dictionary import CohortAlphaFrontierDataDictionary, build_cohort_alpha_frontier_data_dictionary
from .cohort_alpha_frontier_dataset_manifest import CohortAlphaFrontierDatasetManifest, build_cohort_alpha_frontier_dataset_manifest
from .cohort_alpha_frontier_depth import CohortAlphaFrontierDepthAudit, audit_cohort_alpha_frontier_depth
from .cohort_alpha_frontier_boundary_explanations import CohortAlphaFrontierBoundaryExplanationSet, build_cohort_alpha_frontier_boundary_explanations
from .cohort_alpha_frontier_diagnostics import CohortAlphaFrontierDiagnosticReport, build_cohort_alpha_frontier_diagnostics
from .cohort_alpha_frontier_evidence_matrix import CohortAlphaFrontierEvidenceMatrix, build_cohort_alpha_frontier_evidence_matrix
from .cohort_alpha_frontier_failure_injection import CohortAlphaFrontierFailureReport, assess_cohort_alpha_frontier_failures
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation, evaluate_cohort_alpha_frontier_fixture
from .cohort_alpha_frontier_governance import CohortAlphaFrontierLineage, CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy, CohortAlphaFrontierQualityGate, CohortAlphaFrontierReconciliation, CohortAlphaFrontierReleaseBundle, CohortAlphaFrontierReleaseManifest, CohortAlphaFrontierReplayReceipt, CohortAlphaFrontierReviewQueue, assemble_cohort_alpha_frontier_bundle, build_cohort_alpha_frontier_lineage, build_cohort_alpha_frontier_provenance, build_cohort_alpha_frontier_release_manifest, build_cohort_alpha_frontier_review_queue, evaluate_cohort_alpha_frontier_quality, materialize_cohort_alpha_frontier_policy, measure_cohort_alpha_frontier, reconcile_cohort_alpha_frontier, replay_cohort_alpha_frontier
from .cohort_alpha_frontier_integrity import CohortAlphaFrontierIntegrityReport, evaluate_cohort_alpha_frontier_integrity
from .cohort_alpha_frontier_artifact_index import CohortAlphaFrontierArtifactIndex, build_cohort_alpha_frontier_artifact_index
from .cohort_alpha_frontier_boundary_cases import CohortAlphaFrontierBoundaryIndex, build_cohort_alpha_frontier_boundary_index
from .cohort_alpha_frontier_data_freshness import CohortAlphaFrontierFreshnessReport, assess_cohort_alpha_frontier_freshness
from .cohort_alpha_frontier_execution_plan import CohortAlphaFrontierExecutionPlan, build_cohort_alpha_frontier_execution_plan
from .cohort_alpha_frontier_monitoring import CohortAlphaFrontierMonitoringReport, build_cohort_alpha_frontier_monitoring
from .cohort_alpha_frontier_observability import CohortAlphaFrontierObservabilityReport, observe_cohort_alpha_frontier
from .cohort_alpha_frontier_operational import CohortAlphaFrontierOperationalMatrix, build_cohort_alpha_frontier_operational_matrix
from .cohort_alpha_frontier_package import CohortAlphaFrontierPackageManifest, assemble_cohort_alpha_frontier_package
from .cohort_alpha_frontier_export_formats import CohortAlphaFrontierExportReport, build_cohort_alpha_frontier_export_profiles
from .cohort_alpha_frontier_field_validation import CohortAlphaFrontierFieldValidationReport, validate_cohort_alpha_frontier_fields
from .cohort_alpha_frontier_normalization import CohortAlphaFrontierNormalizationReport, normalize_cohort_alpha_frontier_fixture
from .cohort_alpha_frontier_operation_catalog import CohortAlphaFrontierOperationCatalog, build_cohort_alpha_frontier_operation_catalog
from .cohort_alpha_frontier_operation_parameters import CohortAlphaFrontierParameterReport, build_cohort_alpha_frontier_parameter_report
from .cohort_alpha_frontier_partition import CohortAlphaFrontierPartitionSet, build_cohort_alpha_frontier_partitions
from .cohort_alpha_frontier_performance import CohortAlphaFrontierPerformanceReport, measure_cohort_alpha_frontier_performance
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierDataAudit, CohortAlphaFrontierFixture, audit_cohort_alpha_frontier_data, default_cohort_alpha_frontier_fixture
from .cohort_alpha_frontier_recovery import CohortAlphaFrontierRecoveryPlan, build_cohort_alpha_frontier_recovery_plan
from .cohort_alpha_frontier_reproducibility import CohortAlphaFrontierReproducibilityReceipt, build_cohort_alpha_frontier_reproducibility_receipt
from .cohort_alpha_frontier_report import CohortAlphaFrontierReport, build_cohort_alpha_frontier_report
from .cohort_alpha_frontier_retention import CohortAlphaFrontierRetentionPlan, build_cohort_alpha_frontier_retention_plan
from .cohort_alpha_frontier_review_sla import CohortAlphaFrontierReviewSlaReport, build_cohort_alpha_frontier_review_sla
from .cohort_alpha_frontier_review_protocol import CohortAlphaFrontierReviewProtocol, build_cohort_alpha_frontier_review_protocol
from .cohort_alpha_frontier_runbook import CohortAlphaFrontierRunbook, build_cohort_alpha_frontier_runbook
from .cohort_alpha_frontier_runtime_types import CohortAlphaFrontierRuntimeStage
from .cohort_alpha_frontier_safety_controls import CohortAlphaFrontierSafetyReport, evaluate_cohort_alpha_frontier_safety
from .cohort_alpha_frontier_schema import CohortAlphaFrontierSchemaReport, default_cohort_alpha_frontier_schema
from .cohort_alpha_frontier_schema_migrations import CohortAlphaFrontierMigrationPlan, build_cohort_alpha_frontier_migration_plan
from .cohort_alpha_frontier_source_registry import CohortAlphaFrontierSourceRegistry, build_cohort_alpha_frontier_source_registry
from .cohort_alpha_frontier_source_receipt_matrix import CohortAlphaFrontierSourceReceiptMatrix, build_cohort_alpha_frontier_source_receipt_matrix
from .cohort_alpha_frontier_schema_projection import CohortAlphaFrontierSchemaProjectionReport, build_cohort_alpha_frontier_schema_projection
from .cohort_alpha_frontier_state_distribution import CohortAlphaFrontierStateDistribution, build_cohort_alpha_frontier_state_distribution
from .cohort_alpha_frontier_state_machine import CohortAlphaFrontierLifecycleReport, build_cohort_alpha_frontier_lifecycle
from .cohort_alpha_frontier_test_vectors import CohortAlphaFrontierTestVectorSet, build_cohort_alpha_frontier_test_vectors
from .cohort_alpha_frontier_provenance_ledger import CohortAlphaFrontierProvenanceLedger, build_cohort_alpha_frontier_provenance_ledger
from .cohort_alpha_frontier_release_checks import CohortAlphaFrontierReleaseCheckReport, evaluate_cohort_alpha_frontier_release_checks
from .cohort_alpha_frontier_release_notes import CohortAlphaFrontierReleaseNotes, build_cohort_alpha_frontier_release_notes
from .cohort_alpha_frontier_quality_summary import CohortAlphaFrontierQualitySummary, summarize_cohort_alpha_frontier_quality
from .cohort_alpha_frontier_transcript import CohortAlphaFrontierTranscript, build_cohort_alpha_frontier_transcript
from .cohort_alpha_frontier_summary import CohortAlphaFrontierSummary, build_cohort_alpha_frontier_summary
from .cohort_alpha_frontier_thresholds import CohortAlphaFrontierThresholdReport, assess_cohort_alpha_frontier_thresholds
from .cohort_alpha_frontier_traces import CohortAlphaFrontierTraceLedger, build_cohort_alpha_frontier_trace_ledger
from .cohort_alpha_frontier_validation_matrix import CohortAlphaFrontierValidationMatrix, build_cohort_alpha_frontier_validation_matrix
from .cohort_alpha_frontier_views import CohortAlphaFrontierViewSet, build_cohort_alpha_frontier_views
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRuntimeReport:
    fixture: CohortAlphaFrontierFixture
    data_audit: CohortAlphaFrontierDataAudit
    evaluation: CohortAlphaFrontierEvaluation
    adapters: CohortAlphaFrontierAdapterRegistry
    contracts: CohortAlphaFrontierContractRegistry
    schema: CohortAlphaFrontierSchemaReport
    source_registry: CohortAlphaFrontierSourceRegistry
    integrity: CohortAlphaFrontierIntegrityReport
    metrics: CohortAlphaFrontierMetrics
    lineage: CohortAlphaFrontierLineage
    policy: CohortAlphaFrontierPolicy
    reconciliation: CohortAlphaFrontierReconciliation
    review: CohortAlphaFrontierReviewQueue
    quality: CohortAlphaFrontierQualityGate
    thresholds: CohortAlphaFrontierThresholdReport
    calibration: CohortAlphaFrontierCalibrationReport
    coverage: CohortAlphaFrontierControlCoverage
    failures: CohortAlphaFrontierFailureReport
    recovery: CohortAlphaFrontierRecoveryPlan
    performance: CohortAlphaFrontierPerformanceReport
    migration: CohortAlphaFrontierMigrationPlan
    dataset: CohortAlphaFrontierDatasetManifest
    dictionary: CohortAlphaFrontierDataDictionary
    bundle: CohortAlphaFrontierReleaseBundle
    replay: CohortAlphaFrontierReplayReceipt
    manifest: CohortAlphaFrontierReleaseManifest
    package: CohortAlphaFrontierPackageManifest
    views: CohortAlphaFrontierViewSet
    report: CohortAlphaFrontierReport
    runbook: CohortAlphaFrontierRunbook
    accessibility: CohortAlphaFrontierAccessibilityReport
    assurance: CohortAlphaFrontierAssuranceReport
    retention: CohortAlphaFrontierRetentionPlan
    claims: CohortAlphaFrontierClaimEvidenceReport
    compatibility: CohortAlphaFrontierCompatibilityReport
    monitoring: CohortAlphaFrontierMonitoringReport
    evidence: CohortAlphaFrontierEvidenceMatrix
    safety: CohortAlphaFrontierSafetyReport
    depth: CohortAlphaFrontierDepthAudit
    validation: CohortAlphaFrontierValidationMatrix
    traces: CohortAlphaFrontierTraceLedger
    diagnostics: CohortAlphaFrontierDiagnosticReport
    operational: CohortAlphaFrontierOperationalMatrix
    observability: CohortAlphaFrontierObservabilityReport
    summary: CohortAlphaFrontierSummary
    change_control: CohortAlphaFrontierChangeControl
    audit_log: CohortAlphaFrontierAuditLog
    extended: tuple[tuple[str, Any], ...]
    stages: tuple[CohortAlphaFrontierRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        payload = {item.name: getattr(self, item.name) for item in fields(self)}
        payload["adapters"] = self.adapters.to_dict()
        return jsonable(payload)

    def to_markdown(self) -> str:
        return self.report.to_markdown()


def _stage(stage_id: str, output: Any, accepted: bool | None = None, detail: str = "") -> CohortAlphaFrontierRuntimeStage:
    if hasattr(output, "to_dict"):
        serialized = output.to_dict()
    else:
        serialized = jsonable(output)
    address = content_hash(serialized, prefix="alpha-runtime-stage")
    return CohortAlphaFrontierRuntimeStage(0, stage_id, bool(accepted if accepted is not None else getattr(output, "accepted", True)), address, detail or stage_id)


def run_cohort_alpha_frontier_pipeline(fixture: CohortAlphaFrontierFixture | None = None) -> CohortAlphaFrontierRuntimeReport:
    value = fixture or default_cohort_alpha_frontier_fixture()
    data_audit = audit_cohort_alpha_frontier_data(value)
    evaluation = evaluate_cohort_alpha_frontier_fixture(value)
    adapters = default_cohort_alpha_frontier_adapters()
    contracts = default_cohort_alpha_frontier_contracts()
    schema = default_cohort_alpha_frontier_schema()
    source_registry = build_cohort_alpha_frontier_source_registry(value)
    integrity = evaluate_cohort_alpha_frontier_integrity(value, evaluation)
    metrics = measure_cohort_alpha_frontier(evaluation)
    lineage = build_cohort_alpha_frontier_lineage(value, evaluation)
    provenance = build_cohort_alpha_frontier_provenance(value, evaluation)
    policy = materialize_cohort_alpha_frontier_policy(evaluation, contracts)
    reconciliation = reconcile_cohort_alpha_frontier(value, evaluation, policy)
    review = build_cohort_alpha_frontier_review_queue(evaluation, policy)
    quality = evaluate_cohort_alpha_frontier_quality(value, evaluation, contracts, schema, lineage, reconciliation)
    thresholds = assess_cohort_alpha_frontier_thresholds(evaluation)
    calibration = build_cohort_alpha_frontier_calibration(thresholds)
    coverage = build_cohort_alpha_frontier_control_coverage(value, evaluation)
    failures = assess_cohort_alpha_frontier_failures(value, evaluation)
    recovery = build_cohort_alpha_frontier_recovery_plan(failures)
    performance = measure_cohort_alpha_frontier_performance(evaluation)
    migration = build_cohort_alpha_frontier_migration_plan()
    dataset = build_cohort_alpha_frontier_dataset_manifest(value, data_audit)
    dictionary = build_cohort_alpha_frontier_data_dictionary(schema)
    bundle = assemble_cohort_alpha_frontier_bundle(value, evaluation, metrics, policy, reconciliation, quality)
    replay = replay_cohort_alpha_frontier(value)
    manifest = build_cohort_alpha_frontier_release_manifest(bundle, quality, replay)
    package = assemble_cohort_alpha_frontier_package(bundle)
    views = build_cohort_alpha_frontier_views(evaluation, policy, review)
    report = build_cohort_alpha_frontier_report(evaluation, metrics, policy, review, quality, manifest)
    runbook = build_cohort_alpha_frontier_runbook(quality, manifest)
    accessibility = build_cohort_alpha_frontier_accessibility(report)
    assurance = evaluate_cohort_alpha_frontier_assurance(quality, lineage, replay, integrity, policy)
    retention = build_cohort_alpha_frontier_retention_plan(package)
    claims = build_cohort_alpha_frontier_claim_evidence(value, policy)
    compatibility = build_cohort_alpha_frontier_compatibility(package)
    monitoring = build_cohort_alpha_frontier_monitoring(metrics, policy)
    evidence = build_cohort_alpha_frontier_evidence_matrix(value, evaluation, policy, lineage, quality)
    safety = evaluate_cohort_alpha_frontier_safety(policy, quality)
    depth = audit_cohort_alpha_frontier_depth(value, evaluation, metrics, lineage, quality)
    validation = build_cohort_alpha_frontier_validation_matrix(contracts, evaluation)
    traces = build_cohort_alpha_frontier_trace_ledger(evaluation, policy, reconciliation)
    diagnostics = build_cohort_alpha_frontier_diagnostics(evaluation, metrics, policy, reconciliation)
    operational = build_cohort_alpha_frontier_operational_matrix(policy)
    normalization = normalize_cohort_alpha_frontier_fixture(value)
    field_validation = validate_cohort_alpha_frontier_fields(value, adapters)
    catalog = build_cohort_alpha_frontier_operation_catalog(contracts)
    partitions = build_cohort_alpha_frontier_partitions(policy)
    boundary_index = build_cohort_alpha_frontier_boundary_index(evaluation)
    boundary_explanations = build_cohort_alpha_frontier_boundary_explanations(evaluation)
    source_receipts = build_cohort_alpha_frontier_source_receipt_matrix(value)
    state_distribution = build_cohort_alpha_frontier_state_distribution(evaluation)
    parameter_report = build_cohort_alpha_frontier_parameter_report(calibration)
    schema_projection = build_cohort_alpha_frontier_schema_projection(schema)
    api_contract = default_cohort_alpha_frontier_api_contract()
    claim_dictionary = build_cohort_alpha_frontier_claim_dictionary(build_cohort_alpha_frontier_claim_boundary(contracts))
    freshness = assess_cohort_alpha_frontier_freshness(value)
    review_protocol = build_cohort_alpha_frontier_review_protocol(review)
    lifecycle = build_cohort_alpha_frontier_lifecycle(manifest.ready)
    provenance_ledger = build_cohort_alpha_frontier_provenance_ledger(lineage)
    test_vectors = build_cohort_alpha_frontier_test_vectors(evaluation)
    quality_summary = summarize_cohort_alpha_frontier_quality(quality)
    runbook_plan = build_cohort_alpha_frontier_execution_plan(runbook)
    release_notes = build_cohort_alpha_frontier_release_notes(manifest)
    artifact_index = build_cohort_alpha_frontier_artifact_index(package)
    export_profiles = build_cohort_alpha_frontier_export_profiles(report)
    extended = (("normalization", normalization), ("field_validation", field_validation), ("catalog", catalog), ("partitions", partitions), ("boundary_index", boundary_index), ("boundary_explanations", boundary_explanations), ("source_receipts", source_receipts), ("state_distribution", state_distribution), ("parameter_report", parameter_report), ("schema_projection", schema_projection), ("api_contract", api_contract), ("claim_dictionary", claim_dictionary), ("freshness", freshness), ("review_protocol", review_protocol), ("lifecycle", lifecycle), ("provenance_ledger", provenance_ledger), ("test_vectors", test_vectors), ("quality_summary", quality_summary), ("runbook_plan", runbook_plan), ("release_notes", release_notes), ("artifact_index", artifact_index), ("export_profiles", export_profiles))
    provisional = tuple(_stage(stage_id, output) for stage_id, output in (("fixture", value), ("data_audit", data_audit), ("evaluation", evaluation), ("adapters", adapters), ("contracts", contracts), ("schema", schema), ("source_registry", source_registry), ("integrity", integrity), ("metrics", metrics), ("lineage", lineage), ("provenance", provenance), ("policy", policy), ("reconciliation", reconciliation), ("review", review), ("quality", quality), ("thresholds", thresholds), ("calibration", calibration), ("coverage", coverage), ("failures", failures), ("recovery", recovery), ("performance", performance), ("migration", migration), ("dataset", dataset), ("dictionary", dictionary), ("bundle", bundle), ("replay", replay), ("manifest", manifest), ("package", package), ("views", views), ("report", report), ("runbook", runbook), ("accessibility", accessibility), ("assurance", assurance), ("retention", retention), ("claims", claims), ("compatibility", compatibility), ("monitoring", monitoring), ("evidence", evidence), ("safety", safety), ("depth", depth), ("validation", validation), ("traces", traces), ("diagnostics", diagnostics), ("operational", operational)) + extended)
    stages = tuple(CohortAlphaFrontierRuntimeStage(index, stage.stage_id, stage.accepted, stage.output_address, stage.detail) for index, stage in enumerate(provisional, 1))
    release_checks = evaluate_cohort_alpha_frontier_release_checks(stages)
    extended = extended + (("release_checks", release_checks),)
    observability = observe_cohort_alpha_frontier(value.fixture_id, stages, emitted_at="2026-08-22T00:00:00Z")
    summary = build_cohort_alpha_frontier_summary(metrics, policy, quality)
    change_control = build_cohort_alpha_frontier_change_control(migration)
    audit_log = build_cohort_alpha_frontier_audit_log(stages)
    final_stages = stages + (_stage("release_checks", release_checks), _stage("observability", observability), _stage("summary", summary), _stage("change_control", change_control), _stage("audit_log", audit_log))
    final_stages = tuple(CohortAlphaFrontierRuntimeStage(index, stage.stage_id, stage.accepted, stage.output_address, stage.detail) for index, stage in enumerate(final_stages, 1))
    accepted = all(stage.accepted for stage in final_stages) and manifest.ready and package.accepted
    addresses = {"fixture": value.content_address, "evaluation": evaluation.content_address, "manifest": manifest.content_address, "package": package.content_address, "stages": final_stages, "accepted": accepted, "provenance": provenance.content_address}
    return CohortAlphaFrontierRuntimeReport(value, data_audit, evaluation, adapters, contracts, schema, source_registry, integrity, metrics, lineage, policy, reconciliation, review, quality, thresholds, calibration, coverage, failures, recovery, performance, migration, dataset, dictionary, bundle, replay, manifest, package, views, report, runbook, accessibility, assurance, retention, claims, compatibility, monitoring, evidence, safety, depth, validation, traces, diagnostics, operational, observability, summary, change_control, audit_log, extended, final_stages, accepted, content_hash(addresses, prefix="alpha-runtime"))


__all__ = ["CohortAlphaFrontierRuntimeReport", "run_cohort_alpha_frontier_pipeline"]
