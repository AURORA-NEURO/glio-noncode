"""Complete local runtime for D14 C13-C16 evidence lifecycle release."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .evidence_release_frontier_access import EvidenceReleaseAccessManifest, build_evidence_release_access_manifest
from .evidence_release_frontier_adapters import EvidenceReleaseAdapterRegistry, build_evidence_release_adapters
from .evidence_release_frontier_artifacts import EvidenceReleaseArtifactInventory, build_evidence_release_artifact_inventory
from .evidence_release_frontier_assurance import EvidenceReleaseAssuranceSummary, build_evidence_release_assurance_summary
from .evidence_release_frontier_audit_log import EvidenceReleaseAuditLog, build_evidence_release_audit_log
from .evidence_release_frontier_bundle import EvidenceReleaseBundle, assemble_evidence_release_bundle
from .evidence_release_frontier_claim_boundary import EvidenceReleaseClaimBoundary, evaluate_evidence_release_claim_boundary
from .evidence_release_frontier_compliance import EvidenceReleaseComplianceReport, evaluate_evidence_release_compliance
from .evidence_release_frontier_contracts import EvidenceReleaseEvaluation, EvidenceReleaseFixture
from .evidence_release_frontier_controls import EvidenceReleaseControlCoverage, build_evidence_release_control_coverage
from .evidence_release_frontier_data_dictionary import EvidenceReleaseDataDictionary, default_evidence_release_data_dictionary
from .evidence_release_frontier_depth import EvidenceReleaseDepthAudit, audit_evidence_release_depth
from .evidence_release_frontier_diagnostics import EvidenceReleaseDiagnostics, diagnose_evidence_release
from .evidence_release_frontier_evidence_matrix import EvidenceReleaseEvidenceMatrix, build_evidence_release_evidence_matrix
from .evidence_release_frontier_execution_plan import EvidenceReleaseExecutionPlan, build_evidence_release_execution_plan
from .evidence_release_frontier_failure_injection import EvidenceReleaseFailureReport, run_evidence_release_failure_injections
from .evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from .evidence_release_frontier_freshness import EvidenceReleaseFreshnessReport, evaluate_evidence_release_freshness
from .evidence_release_frontier_handoff import EvidenceReleaseHandoff, build_evidence_release_handoff
from .evidence_release_frontier_integrity import EvidenceReleaseIntegrityReport, evaluate_evidence_release_integrity
from .evidence_release_frontier_lineage import EvidenceReleaseLineage, build_evidence_release_lineage
from .evidence_release_frontier_metrics import EvidenceReleaseMetrics, measure_evidence_release
from .evidence_release_frontier_observability import EvidenceReleaseTrace, build_evidence_release_trace
from .evidence_release_frontier_operational import EvidenceReleaseOperationalMatrix, build_evidence_release_operational_matrix
from .evidence_release_frontier_package import EvidenceReleasePackageManifest, build_evidence_release_package_manifest
from .evidence_release_frontier_partition import EvidenceReleasePartitionReport, build_evidence_release_partitions
from .evidence_release_frontier_performance import EvidenceReleasePerformanceBudget, build_evidence_release_performance_budget
from .evidence_release_frontier_policy import EvidenceReleasePolicy, default_evidence_release_policy
from .evidence_release_frontier_provenance import EvidenceReleaseProvenance, build_evidence_release_provenance
from .evidence_release_frontier_provenance_check import EvidenceReleaseProvenanceCheck, evaluate_evidence_release_provenance
from .evidence_release_frontier_query import EvidenceReleaseQueryResult, query_evidence_release
from .evidence_release_frontier_reconciliation import EvidenceReleaseReconciliation, reconcile_evidence_release
from .evidence_release_frontier_recovery import EvidenceReleaseRecoveryPlan, build_evidence_release_recovery_plan
from .evidence_release_frontier_release import EvidenceReleaseManifest, build_evidence_release_manifest
from .evidence_release_frontier_release_checks import EvidenceReleaseCheckReport, evaluate_evidence_release_checks
from .evidence_release_frontier_replay import EvidenceReleaseReplayReport, replay_evidence_release_evaluation
from .evidence_release_frontier_reproducibility import EvidenceReleaseReproducibilityPacket, build_evidence_release_reproducibility_packet
from .evidence_release_frontier_review_protocol import EvidenceReleaseReviewProtocol, build_evidence_release_review_protocol
from .evidence_release_frontier_review_queue import EvidenceReleaseReviewQueue, build_evidence_release_review_queue
from .evidence_release_frontier_review_sla import EvidenceReleaseReviewSla, build_evidence_release_review_sla
from .evidence_release_frontier_run_manifest import EvidenceReleaseRunManifest, build_evidence_release_run_manifest
from .evidence_release_frontier_runbook import EvidenceReleaseRunbook, build_evidence_release_runbook, runbook_is_executable
from .evidence_release_frontier_scenario_matrix import EvidenceReleaseScenarioMatrix, evaluate_evidence_release_scenarios
from .evidence_release_frontier_schema import EvidenceReleaseSchema, default_evidence_release_frontier_schema
from .evidence_release_frontier_source_registry import EvidenceReleaseSourceRegistry, build_evidence_release_source_registry
from .evidence_release_frontier_summary import EvidenceReleaseSummary, build_evidence_release_summary
from .evidence_release_frontier_thresholds import EvidenceReleaseThresholdReport, build_evidence_release_threshold_report
from .evidence_release_frontier_transcript import EvidenceReleaseTranscript, build_evidence_release_transcript
from .evidence_release_frontier_validation_matrix import EvidenceReleaseValidationMatrix, build_evidence_release_validation_matrix
from .evidence_release_frontier_views import EvidenceReleaseView, build_evidence_release_view
from .evidence_release_frontier_public_data import EvidenceReleaseDataAudit, audit_evidence_release_frontier_data, default_evidence_release_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseRuntimeStage:
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
class EvidenceReleaseRuntimeReport:
    run_id: str
    stages: tuple[EvidenceReleaseRuntimeStage, ...]
    fixture: EvidenceReleaseFixture
    audit: EvidenceReleaseDataAudit
    adapters: EvidenceReleaseAdapterRegistry
    schema: EvidenceReleaseSchema
    evaluation: EvidenceReleaseEvaluation
    metrics: EvidenceReleaseMetrics
    policy: EvidenceReleasePolicy
    lineage: EvidenceReleaseLineage
    reconciliation: EvidenceReleaseReconciliation
    quality: Any
    replay: EvidenceReleaseReplayReport
    reproducibility: EvidenceReleaseReproducibilityPacket
    release: EvidenceReleaseManifest
    artifacts: EvidenceReleaseArtifactInventory
    view: EvidenceReleaseView
    queue: EvidenceReleaseReviewQueue
    sla: EvidenceReleaseReviewSla
    review_protocol: EvidenceReleaseReviewProtocol
    handoff: EvidenceReleaseHandoff
    integrity: EvidenceReleaseIntegrityReport
    depth: EvidenceReleaseDepthAudit
    thresholds: EvidenceReleaseThresholdReport
    scenarios: EvidenceReleaseScenarioMatrix
    controls: EvidenceReleaseControlCoverage
    validation: EvidenceReleaseValidationMatrix
    evidence: EvidenceReleaseEvidenceMatrix
    assurance: EvidenceReleaseAssuranceSummary
    claim_boundary: EvidenceReleaseClaimBoundary
    failure_injection: EvidenceReleaseFailureReport
    recovery: EvidenceReleaseRecoveryPlan
    performance: EvidenceReleasePerformanceBudget
    operational: EvidenceReleaseOperationalMatrix
    compliance: EvidenceReleaseComplianceReport
    diagnostics: EvidenceReleaseDiagnostics
    query: EvidenceReleaseQueryResult
    partitions: EvidenceReleasePartitionReport
    resources: Any
    plan: EvidenceReleaseExecutionPlan
    provenance: EvidenceReleaseProvenance
    provenance_check: EvidenceReleaseProvenanceCheck
    source_registry: EvidenceReleaseSourceRegistry
    access: EvidenceReleaseAccessManifest
    freshness: EvidenceReleaseFreshnessReport
    compatibility: Any
    release_checks: EvidenceReleaseCheckReport
    runbook: EvidenceReleaseRunbook
    run_manifest: EvidenceReleaseRunManifest
    audit_log: EvidenceReleaseAuditLog
    transcript: EvidenceReleaseTranscript
    summary: EvidenceReleaseSummary
    data_dictionary: EvidenceReleaseDataDictionary
    package: EvidenceReleasePackageManifest
    bundle: EvidenceReleaseBundle
    trace: EvidenceReleaseTrace
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.stage_id for stage in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_evidence_release_runtime(fixture: EvidenceReleaseFixture | None = None, *, run_id: str = "evidence-release-runtime") -> EvidenceReleaseRuntimeReport:
    fixture = fixture or default_evidence_release_frontier_fixture()
    stages: list[EvidenceReleaseRuntimeStage] = []

    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        elapsed = round((perf_counter() - started) * 1000, 3)
        output_address = getattr(result, "content_address", None) or content_hash(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": elapsed, "output_address": output_address, "detail": detail}
        stages.append(EvidenceReleaseRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", lambda: audit_evidence_release_frontier_data(fixture), "audit public aggregate source and row receipts")
    source_registry = stage("source-registry", lambda: build_evidence_release_source_registry(fixture), "close public source identities")
    adapters = stage("adapters", build_evidence_release_adapters, "materialize four transition adapters")
    schema = stage("schema", default_evidence_release_frontier_schema, "materialize required input and output fields")
    evaluation = stage("fixture-evaluation", lambda: evaluate_evidence_release_fixture(fixture), "execute positive and control rows")
    metrics = stage("metrics", lambda: measure_evidence_release(evaluation), "measure state and issue distributions")
    policy = stage("policy", default_evidence_release_policy, "apply lifecycle claim boundary")
    lineage = stage("lineage", lambda: build_evidence_release_lineage(fixture, evaluation), "connect sources records and executions")
    reconciliation = stage("reconciliation", lambda: reconcile_evidence_release(fixture, evaluation), "compare expected and observed states")
    quality = stage("quality-gate", lambda: __import__("glio_noncode.evidence_release_frontier_quality_gate", fromlist=["run_evidence_release_quality_gate"]).run_evidence_release_quality_gate(audit, evaluation, adapters, schema, reconciliation), "run blocking quality checks")
    replay = stage("replay", lambda: replay_evidence_release_evaluation(fixture, evaluation), "replay deterministic evaluation")
    reproducibility = stage("reproducibility", lambda: build_evidence_release_reproducibility_packet(fixture, evaluation, replay, lineage), "join replay and lineage receipts")
    release = stage("release", lambda: build_evidence_release_manifest(fixture, evaluation, quality, lineage, replay, release_id=run_id), "build bounded research release manifest")
    artifacts = stage("artifacts", lambda: build_evidence_release_artifact_inventory(fixture, release), "inventory release artifacts")
    view = stage("review-view", lambda: build_evidence_release_view(evaluation), "build stable review view")
    queue = stage("review-queue", lambda: build_evidence_release_review_queue(evaluation), "route non-terminal rows")
    sla = stage("review-sla", lambda: build_evidence_release_review_sla(queue), "assign response bands")
    review_protocol = stage("review-protocol", lambda: build_evidence_release_review_protocol(queue), "materialize review instructions")
    handoff = stage("handoff", lambda: build_evidence_release_handoff(fixture, evaluation, metrics, queue), "assemble bounded handoff")
    integrity = stage("integrity", lambda: evaluate_evidence_release_integrity(fixture, evaluation), "recompute identity and nested addresses")
    depth = stage("depth", lambda: audit_evidence_release_depth(fixture, evaluation), "audit transition planes")
    thresholds = stage("thresholds", build_evidence_release_threshold_report, "probe numeric and state boundaries")
    scenarios = stage("scenario-matrix", lambda: evaluate_evidence_release_scenarios(evaluation), "reconcile expected state scenarios")
    controls = stage("control-coverage", lambda: build_evidence_release_control_coverage(evaluation), "verify negative control coverage")
    validation = stage("validation-matrix", lambda: build_evidence_release_validation_matrix(evaluation), "cover five validation planes")
    evidence = stage("evidence-matrix", lambda: build_evidence_release_evidence_matrix(fixture, evaluation), "close six evidence joins")
    assurance = stage("assurance", lambda: build_evidence_release_assurance_summary(quality, depth, reconciliation), "combine quality depth and integrity")
    claim_boundary = stage("claim-boundary", lambda: evaluate_evidence_release_claim_boundary(evaluation), "enforce lifecycle wording boundary")
    failure_injection = stage("failure-injection", run_evidence_release_failure_injections, "rehearse malformed and unverifiable inputs")
    recovery = stage("recovery", lambda: build_evidence_release_recovery_plan(evaluation), "map states to safe recovery actions")
    performance = stage("performance", lambda: build_evidence_release_performance_budget(evaluation), "close local resource budget")
    operational = stage("operational", lambda: build_evidence_release_operational_matrix(evaluation), "map states to review actions")
    compliance = stage("compliance", lambda: evaluate_evidence_release_compliance(fixture), "audit public aggregate boundary")
    diagnostics = stage("diagnostics", lambda: diagnose_evidence_release(evaluation), "materialize issue findings")
    query = stage("query", lambda: query_evidence_release(evaluation, "review"), "exercise deterministic query index")
    partitions = stage("partitions", lambda: build_evidence_release_partitions(evaluation), "partition rows by capability")
    resources = stage("resource-accounting", lambda: __import__("glio_noncode.evidence_release_frontier_resource_accounting", fromlist=["account_evidence_release_resources"]).account_evidence_release_resources(evaluation), "account bounded output resources")
    plan = stage("execution-plan", build_evidence_release_execution_plan, "build dependency-safe plan")
    provenance = stage("provenance", lambda: build_evidence_release_provenance(run_id, fixture, plan, policy), "record immutable run provenance")
    provenance_check = stage("provenance-check", lambda: evaluate_evidence_release_provenance(fixture), "verify public receipt closure")
    access = stage("access", lambda: build_evidence_release_access_manifest(fixture), "describe public access boundary")
    freshness = stage("freshness", lambda: evaluate_evidence_release_freshness(fixture), "check declared source receipt versions")
    compatibility = stage("compatibility", lambda: __import__("glio_noncode.evidence_release_frontier_compatibility", fromlist=["evaluate_evidence_release_compatibility"]).evaluate_evidence_release_compatibility(), "check contract runtime compatibility")
    release_checks = stage("release-checks", lambda: evaluate_evidence_release_checks(quality, integrity, compatibility), "independently check release gates")
    runbook = stage("runbook", build_evidence_release_runbook, "materialize executable runbook")
    run_manifest = stage("run-manifest", lambda: build_evidence_release_run_manifest(run_id, plan, provenance, tuple(item.stage_id for item in stages)), "join plan provenance and stage list")
    audit_log = stage("audit-log", lambda: build_evidence_release_audit_log(tuple(item.stage_id for item in stages)), "build append-only stage log")
    transcript = stage("transcript", lambda: build_evidence_release_transcript(tuple(item.stage_id for item in stages)), "render ordered transcript")
    summary = stage("summary", lambda: build_evidence_release_summary(evaluation, metrics, release), "build release summary")
    data_dictionary = stage("data-dictionary", default_evidence_release_data_dictionary, "describe stable artifact fields")
    package = stage("package", lambda: build_evidence_release_package_manifest(release, artifacts), "build package manifest")
    bundle = stage("bundle", lambda: assemble_evidence_release_bundle(package, artifacts, summary), "assemble safe release bundle")
    trace = stage("observability", lambda: build_evidence_release_trace(run_id, tuple({"stage_id": item.stage_id, "state": item.state, "output_address": item.output_address, "detail": item.detail} for item in stages), accepted=quality.accepted), "emit ordered structured trace")
    accepted = all((audit.accepted, source_registry.accepted, evaluation.accepted, quality.accepted, lineage.closed, reconciliation.accepted, replay.deterministic, reproducibility.complete, release.accepted, artifacts.complete, queue.accepted, handoff.accepted, integrity.accepted, depth.accepted, thresholds.accepted, scenarios.accepted, controls.accepted, validation.accepted, evidence.accepted, assurance.accepted, claim_boundary.accepted, failure_injection.accepted, performance.bounded, operational.accepted, compliance.accepted, diagnostics.accepted, partitions.accepted, resources.bounded, provenance_check.accepted, release_checks.passed, runbook_is_executable(runbook), run_manifest.accepted, audit_log.contiguous, transcript.accepted, summary.accepted, package.complete, bundle.accepted, trace.accepted))
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "audit": audit, "adapters": adapters, "schema": schema, "evaluation": evaluation, "metrics": metrics, "policy": policy, "lineage": lineage, "reconciliation": reconciliation, "quality": quality, "replay": replay, "reproducibility": reproducibility, "release": release, "artifacts": artifacts, "view": view, "queue": queue, "sla": sla, "review_protocol": review_protocol, "handoff": handoff, "integrity": integrity, "depth": depth, "thresholds": thresholds, "scenarios": scenarios, "controls": controls, "validation": validation, "evidence": evidence, "assurance": assurance, "claim_boundary": claim_boundary, "failure_injection": failure_injection, "recovery": recovery, "performance": performance, "operational": operational, "compliance": compliance, "diagnostics": diagnostics, "query": query, "partitions": partitions, "resources": resources, "plan": plan, "provenance": provenance, "provenance_check": provenance_check, "source_registry": source_registry, "access": access, "freshness": freshness, "compatibility": compatibility, "release_checks": release_checks, "runbook": runbook, "run_manifest": run_manifest, "audit_log": audit_log, "transcript": transcript, "summary": summary, "data_dictionary": data_dictionary, "package": package, "bundle": bundle, "trace": trace, "accepted": accepted}
    return EvidenceReleaseRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseRuntimeReport", "EvidenceReleaseRuntimeStage", "run_evidence_release_runtime"]
