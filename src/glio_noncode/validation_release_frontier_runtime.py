"""End-to-end local runtime for D13 C13-C16 validation-release planning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_access import ValidationReleaseAccessManifest, build_validation_release_access_manifest
from .validation_release_frontier_adapters import ValidationReleaseAdapterRegistry, build_validation_release_adapters
from .validation_release_frontier_artifacts import ValidationReleaseArtifactInventory, build_validation_release_artifact_inventory
from .validation_release_frontier_assurance import ValidationReleaseAssuranceSummary, build_validation_release_assurance_summary
from .validation_release_frontier_audit_log import ValidationReleaseAuditLog, build_validation_release_audit_log
from .validation_release_frontier_bundle import ValidationReleaseBundle, assemble_validation_release_bundle
from .validation_release_frontier_compatibility import ValidationReleaseCompatibility, evaluate_validation_release_compatibility
from .validation_release_frontier_compliance import ValidationReleaseComplianceReport, evaluate_validation_release_compliance
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture
from .validation_release_frontier_controls import ValidationReleaseControlCoverage, build_validation_release_control_coverage
from .validation_release_frontier_claim_boundary import ValidationReleaseClaimBoundary, evaluate_validation_release_claim_boundary
from .validation_release_frontier_depth import ValidationReleaseDepthAudit, audit_validation_release_depth
from .validation_release_frontier_diagnostics import ValidationReleaseDiagnostics, diagnose_validation_release
from .validation_release_frontier_evidence_matrix import ValidationReleaseEvidenceMatrix, build_validation_release_evidence_matrix
from .validation_release_frontier_execution_plan import ValidationReleaseExecutionPlan, build_validation_release_execution_plan
from .validation_release_frontier_failure_injection import ValidationReleaseFailureReport, run_validation_release_failure_injections
from .validation_release_frontier_fixture_eval import evaluate_validation_release_fixture
from .validation_release_frontier_freshness import ValidationReleaseFreshnessReport, evaluate_validation_release_freshness
from .validation_release_frontier_handoff import ValidationReleaseHandoff, build_validation_release_handoff
from .validation_release_frontier_integrity import ValidationReleaseIntegrityReport, evaluate_validation_release_integrity
from .validation_release_frontier_invariants import ValidationReleaseInvariantReport, evaluate_validation_release_invariants
from .validation_release_frontier_lineage import ValidationReleaseLineage, build_validation_release_lineage
from .validation_release_frontier_metrics import ValidationReleaseMetrics, measure_validation_release
from .validation_release_frontier_observability import ValidationReleaseTrace, build_validation_release_trace
from .validation_release_frontier_operational import ValidationReleaseOperationalMatrix, build_validation_release_operational_matrix
from .validation_release_frontier_package import ValidationReleasePackageManifest, build_validation_release_package_manifest
from .validation_release_frontier_performance import ValidationReleasePerformanceBudget, build_validation_release_performance_budget
from .validation_release_frontier_policy import ValidationReleasePolicy, default_validation_release_policy
from .validation_release_frontier_public_data import ValidationReleaseDataAudit, audit_validation_release_frontier_data, default_validation_release_frontier_fixture
from .validation_release_frontier_quality_gate import ValidationReleaseQualityReport, run_validation_release_quality_gate
from .validation_release_frontier_query import ValidationReleaseQueryResult, query_validation_release
from .validation_release_frontier_reconciliation import ValidationReleaseReconciliation, reconcile_validation_release
from .validation_release_frontier_recovery import ValidationReleaseRecoveryPlan, build_validation_release_recovery_plan
from .validation_release_frontier_release import ValidationReleaseManifest, build_validation_release_manifest
from .validation_release_frontier_release_checks import ValidationReleaseCheckReport, evaluate_validation_release_checks
from .validation_release_frontier_replay import ValidationReleaseReplayReport, replay_validation_release_evaluation
from .validation_release_frontier_reproducibility import ValidationReleaseReproducibilityPacket, build_validation_release_reproducibility_packet
from .validation_release_frontier_review_queue import ValidationReleaseReviewQueue, build_validation_release_review_queue
from .validation_release_frontier_review_protocol import ValidationReleaseReviewProtocol, build_validation_release_review_protocol
from .validation_release_frontier_review_sla import ValidationReleaseReviewSla, build_validation_release_review_sla
from .validation_release_frontier_run_manifest import ValidationReleaseRunManifest, build_validation_release_run_manifest
from .validation_release_frontier_runbook import ValidationReleaseRunbook, build_validation_release_runbook
from .validation_release_frontier_scenario_matrix import ValidationReleaseScenarioMatrix, evaluate_validation_release_scenarios
from .validation_release_frontier_schema import ValidationReleaseSchema, default_validation_release_frontier_schema
from .validation_release_frontier_source_registry import ValidationReleaseSourceRegistry, build_validation_release_source_registry
from .validation_release_frontier_summary import ValidationReleaseSummary, build_validation_release_summary
from .validation_release_frontier_transcript import ValidationReleaseTranscript, build_validation_release_transcript
from .validation_release_frontier_validation_matrix import ValidationReleaseValidationMatrix, build_validation_release_validation_matrix
from .validation_release_frontier_thresholds import ValidationReleaseThresholdReport, build_validation_release_threshold_report
from .validation_release_frontier_views import ValidationReleaseView, build_validation_release_view
from .validation_release_frontier_controls import build_validation_release_control_coverage
from .validation_release_frontier_evidence_matrix import build_validation_release_evidence_matrix
from .validation_release_frontier_partition import ValidationReleasePartitionReport, build_validation_release_partitions
from .validation_release_frontier_resource_accounting import ValidationReleaseResourceReport, account_validation_release_resources
from .validation_release_frontier_provenance import ValidationReleaseProvenance, build_validation_release_provenance
from .validation_release_frontier_invariants import assert_validation_release_invariants
from .validation_release_frontier_runbook import runbook_is_executable


@dataclass(frozen=True, slots=True)
class ValidationReleaseRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    duration_ms: float
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseRuntimeReport:
    run_id: str
    stages: tuple[ValidationReleaseRuntimeStage, ...]
    fixture: ValidationReleaseFixture
    audit: ValidationReleaseDataAudit
    adapters: ValidationReleaseAdapterRegistry
    schema: ValidationReleaseSchema
    evaluation: ValidationReleaseEvaluation
    metrics: ValidationReleaseMetrics
    policy: ValidationReleasePolicy
    lineage: ValidationReleaseLineage
    reconciliation: ValidationReleaseReconciliation
    quality: ValidationReleaseQualityReport
    replay: ValidationReleaseReplayReport
    reproducibility: ValidationReleaseReproducibilityPacket
    release: ValidationReleaseManifest
    artifacts: ValidationReleaseArtifactInventory
    view: ValidationReleaseView
    queue: ValidationReleaseReviewQueue
    sla: ValidationReleaseReviewSla
    review_protocol: ValidationReleaseReviewProtocol
    handoff: ValidationReleaseHandoff
    integrity: ValidationReleaseIntegrityReport
    depth: ValidationReleaseDepthAudit
    thresholds: ValidationReleaseThresholdReport
    scenarios: ValidationReleaseScenarioMatrix
    controls: ValidationReleaseControlCoverage
    validation: ValidationReleaseValidationMatrix
    evidence: ValidationReleaseEvidenceMatrix
    assurance: ValidationReleaseAssuranceSummary
    claim_boundary: ValidationReleaseClaimBoundary
    failure_injection: ValidationReleaseFailureReport
    recovery: ValidationReleaseRecoveryPlan
    performance: ValidationReleasePerformanceBudget
    operational: ValidationReleaseOperationalMatrix
    compliance: ValidationReleaseComplianceReport
    diagnostics: ValidationReleaseDiagnostics
    query: ValidationReleaseQueryResult
    partitions: ValidationReleasePartitionReport
    resources: ValidationReleaseResourceReport
    plan: ValidationReleaseExecutionPlan
    provenance: ValidationReleaseProvenance
    access: ValidationReleaseAccessManifest
    freshness: ValidationReleaseFreshnessReport
    compatibility: ValidationReleaseCompatibility
    release_checks: ValidationReleaseCheckReport
    runbook: ValidationReleaseRunbook
    run_manifest: ValidationReleaseRunManifest
    audit_log: ValidationReleaseAuditLog
    transcript: ValidationReleaseTranscript
    summary: ValidationReleaseSummary
    package: ValidationReleasePackageManifest
    bundle: ValidationReleaseBundle
    trace: ValidationReleaseTrace
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_validation_release_runtime(fixture: ValidationReleaseFixture | None = None, *, run_id: str = "validation-release-runtime") -> ValidationReleaseRuntimeReport:
    fixture = fixture or default_validation_release_frontier_fixture()
    stages: list[ValidationReleaseRuntimeStage] = []

    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        duration = round((perf_counter() - started) * 1000, 3)
        output_address = getattr(result, "content_address", None) or content_hash(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": duration, "output_address": output_address, "detail": detail}
        stages.append(ValidationReleaseRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", lambda: audit_validation_release_frontier_data(fixture), "audit public aggregate source and row receipts")
    adapters = stage("adapters", build_validation_release_adapters, "materialize four operation adapters")
    schema = stage("schema", default_validation_release_frontier_schema, "materialize required input and output fields")
    evaluation = stage("fixture-evaluation", lambda: evaluate_validation_release_fixture(fixture), "execute positive and control rows")
    metrics = stage("metrics", lambda: measure_validation_release(evaluation), "measure state, issue, and operation distributions")
    policy = stage("policy", default_validation_release_policy, "apply research-only policy boundary")
    lineage = stage("lineage", lambda: build_validation_release_lineage(fixture, evaluation), "connect sources, records, and executions")
    reconciliation = stage("reconciliation", lambda: reconcile_validation_release(fixture, evaluation), "compare expected and observed states")
    quality = stage("quality-gate", lambda: run_validation_release_quality_gate(audit, evaluation, adapters, schema, reconciliation), "run blocking quality checks")
    replay = stage("replay", lambda: replay_validation_release_evaluation(fixture, evaluation), "replay deterministic evaluation")
    reproducibility = stage("reproducibility", lambda: build_validation_release_reproducibility_packet(fixture, evaluation, replay, lineage), "join replay and lineage receipts")
    release = stage("release", lambda: build_validation_release_manifest(fixture, evaluation, quality, lineage, replay, release_id=run_id), "build research release manifest")
    artifacts = stage("artifacts", lambda: build_validation_release_artifact_inventory(fixture, release), "inventory release artifacts")
    view = stage("review-view", lambda: build_validation_release_view(evaluation), "build stable review view")
    queue = stage("review-queue", lambda: build_validation_release_review_queue(evaluation), "route non-ready rows")
    sla = stage("review-sla", lambda: build_validation_release_review_sla(queue), "assign response bands")
    review_protocol = stage("review-protocol", lambda: build_validation_release_review_protocol(queue), "materialize review instructions")
    handoff = stage("handoff", lambda: build_validation_release_handoff(fixture, evaluation, metrics, queue), "assemble bounded handoff")
    integrity = stage("integrity", lambda: evaluate_validation_release_integrity(fixture, evaluation), "recompute identity and nested addresses")
    depth = stage("depth", lambda: audit_validation_release_depth(fixture, evaluation), "audit scenarios and evidence planes")
    thresholds = stage("thresholds", build_validation_release_threshold_report, "probe numeric and state boundaries")
    scenarios = stage("scenario-matrix", lambda: evaluate_validation_release_scenarios(evaluation), "replay expected state scenarios")
    controls = stage("control-coverage", lambda: build_validation_release_control_coverage(evaluation), "verify negative control coverage")
    validation = stage("validation-matrix", lambda: build_validation_release_validation_matrix(evaluation), "cover six validation planes")
    evidence = stage("evidence-matrix", lambda: build_validation_release_evidence_matrix(fixture, evaluation), "cover six evidence planes")
    assurance = stage("assurance", lambda: build_validation_release_assurance_summary(quality, depth, reconciliation), "combine quality depth and integrity")
    claim_boundary = stage("claim-boundary", lambda: evaluate_validation_release_claim_boundary(evaluation), "enforce research wording boundary")
    failure_injection = stage("failure-injection", run_validation_release_failure_injections, "rehearse operation failures")
    recovery = stage("recovery", lambda: build_validation_release_recovery_plan(evaluation), "map failures to safe recovery actions")
    performance = stage("performance", lambda: build_validation_release_performance_budget(evaluation), "close local resource budget")
    operational = stage("operational", lambda: build_validation_release_operational_matrix(evaluation), "map states to review actions")
    compliance = stage("compliance", lambda: evaluate_validation_release_compliance(fixture), "audit public aggregate boundary")
    diagnostics = stage("diagnostics", lambda: diagnose_validation_release(evaluation), "materialize issue findings")
    query = stage("query", lambda: query_validation_release(evaluation, "review"), "exercise deterministic query index")
    partitions = stage("partitions", lambda: build_validation_release_partitions(evaluation), "partition rows by operation")
    resources = stage("resource-accounting", lambda: account_validation_release_resources(evaluation), "account bounded output resources")
    plan = stage("execution-plan", build_validation_release_execution_plan, "build dependency-safe plan")
    provenance = stage("provenance", lambda: build_validation_release_provenance(run_id, fixture, plan, policy), "record immutable run provenance")
    access = stage("access", lambda: build_validation_release_access_manifest(fixture), "describe public access boundary")
    freshness = stage("freshness", lambda: evaluate_validation_release_freshness(fixture), "check source receipt freshness")
    compatibility = stage("compatibility", evaluate_validation_release_compatibility, "check contract/runtime compatibility")
    release_checks = stage("release-checks", lambda: evaluate_validation_release_checks(quality, integrity, compatibility), "independently check release gates")
    runbook = stage("runbook", build_validation_release_runbook, "materialize executable runbook")
    run_manifest = stage("run-manifest", lambda: build_validation_release_run_manifest(run_id, plan, provenance, tuple(item.stage_id for item in stages)), "join plan provenance and stage list")
    audit_log = stage("audit-log", lambda: build_validation_release_audit_log(tuple(item.stage_id for item in stages)), "build append-only stage log")
    transcript = stage("transcript", lambda: build_validation_release_transcript(tuple(item.stage_id for item in stages)), "render ordered transcript")
    summary = stage("summary", lambda: build_validation_release_summary(evaluation, metrics, release), "build release summary")
    package = stage("package", lambda: build_validation_release_package_manifest(release, artifacts), "build package manifest")
    bundle = stage("bundle", lambda: assemble_validation_release_bundle(package, artifacts, summary), "assemble safe release bundle")
    trace = stage("observability", lambda: build_validation_release_trace(run_id, tuple({"stage_id": item.stage_id, "state": item.state, "output_address": item.output_address, "detail": item.detail} for item in stages), accepted=quality.accepted), "emit structured stage trace")
    accepted = all((audit.accepted, evaluation.accepted, policy.content_address.startswith("sha256:"), not bool(reconciliation.mismatched_records), quality.accepted, replay.deterministic, reproducibility.complete, release.accepted, artifacts.complete, handoff.accepted, review_protocol.accepted, integrity.accepted, depth.accepted, thresholds.accepted, scenarios.accepted, controls.accepted, validation.accepted, evidence.accepted, assurance.accepted, claim_boundary.accepted, failure_injection.accepted, recovery.accepted, performance.accepted, operational.accepted, compliance.accepted, diagnostics.accepted, partitions.accepted, resources.bounded, release_checks.passed, runbook_is_executable(runbook), run_manifest.accepted, audit_log.contiguous, transcript.accepted, summary.accepted, package.complete, bundle.accepted, trace.accepted))
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "audit": audit, "adapters": adapters, "schema": schema, "evaluation": evaluation, "metrics": metrics, "policy": policy, "lineage": lineage, "reconciliation": reconciliation, "quality": quality, "replay": replay, "reproducibility": reproducibility, "release": release, "artifacts": artifacts, "view": view, "queue": queue, "sla": sla, "review_protocol": review_protocol, "handoff": handoff, "integrity": integrity, "depth": depth, "thresholds": thresholds, "scenarios": scenarios, "controls": controls, "validation": validation, "evidence": evidence, "assurance": assurance, "claim_boundary": claim_boundary, "failure_injection": failure_injection, "recovery": recovery, "performance": performance, "operational": operational, "compliance": compliance, "diagnostics": diagnostics, "query": query, "partitions": partitions, "resources": resources, "plan": plan, "provenance": provenance, "access": access, "freshness": freshness, "compatibility": compatibility, "release_checks": release_checks, "runbook": runbook, "run_manifest": run_manifest, "audit_log": audit_log, "transcript": transcript, "summary": summary, "package": package, "bundle": bundle, "trace": trace, "accepted": accepted}
    return ValidationReleaseRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseRuntimeReport", "ValidationReleaseRuntimeStage", "run_validation_release_runtime"]
