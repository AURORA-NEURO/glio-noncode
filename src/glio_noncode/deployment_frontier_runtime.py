"""End-to-end runtime rehearsal for D16 C13-C16 deployment governance."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .deployment_frontier_access import build_deployment_frontier_access_manifest
from .deployment_frontier_adapters import build_deployment_frontier_adapters
from .deployment_frontier_artifacts import DeploymentFrontierArtifactInventory, build_deployment_frontier_artifact_inventory
from .deployment_frontier_assurance import DeploymentFrontierAssuranceSummary, build_deployment_frontier_assurance_summary
from .deployment_frontier_audit_log import DeploymentFrontierAuditLog, build_deployment_frontier_audit_log
from .deployment_frontier_bundle import DeploymentFrontierReleaseBundle, assemble_deployment_frontier_bundle
from .deployment_frontier_claim_boundary import evaluate_deployment_frontier_claim_boundary
from .deployment_frontier_compatibility import evaluate_deployment_frontier_compatibility
from .deployment_frontier_compliance import evaluate_deployment_frontier_compliance
from .deployment_frontier_contracts import DeploymentFrontierFixture
from .deployment_frontier_depth import DeploymentFrontierDepthAudit, audit_deployment_frontier_depth
from .deployment_frontier_diagnostics import DeploymentFrontierDiagnostics, diagnose_deployment_frontier
from .deployment_frontier_execution_plan import DeploymentFrontierExecutionPlan, build_deployment_frontier_execution_plan
from .deployment_frontier_failure_injection import DeploymentFrontierFailureReport, run_deployment_frontier_failure_injections
from .deployment_frontier_fixture_eval import evaluate_deployment_frontier_fixture
from .deployment_frontier_freshness import DeploymentFrontierFreshnessReport, evaluate_deployment_frontier_freshness
from .deployment_frontier_handoff import DeploymentFrontierHandoff, build_deployment_frontier_handoff
from .deployment_frontier_integrity import DeploymentFrontierIntegrityReport, evaluate_deployment_frontier_integrity
from .deployment_frontier_invariants import DeploymentFrontierInvariantReport, evaluate_deployment_frontier_invariants
from .deployment_frontier_lineage import DeploymentFrontierLineage, build_deployment_frontier_lineage
from .deployment_frontier_metrics import DeploymentFrontierMetrics, measure_deployment_frontier
from .deployment_frontier_observability import DeploymentFrontierTrace, build_deployment_frontier_trace
from .deployment_frontier_operational import DeploymentFrontierOperationalMatrix, build_deployment_frontier_operational_matrix
from .deployment_frontier_package import DeploymentFrontierPackageManifest, build_deployment_frontier_package_manifest
from .deployment_frontier_performance import DeploymentFrontierPerformanceBudget, build_deployment_frontier_performance_budget
from .deployment_frontier_policy import DeploymentFrontierPolicy, default_deployment_frontier_policy
from .deployment_frontier_public_data import DeploymentFrontierDataAudit, audit_deployment_frontier_data, default_deployment_frontier_fixture
from .deployment_frontier_quality_gate import DeploymentFrontierQualityReport, run_deployment_frontier_quality_gate
from .deployment_frontier_reconciliation import DeploymentFrontierReconciliation, reconcile_deployment_frontier
from .deployment_frontier_release import DeploymentFrontierReleaseManifest, build_deployment_frontier_release
from .deployment_frontier_release_checks import DeploymentFrontierReleaseCheckReport, evaluate_deployment_frontier_release_checks
from .deployment_frontier_replay import DeploymentFrontierReplayReport, replay_deployment_frontier_evaluation
from .deployment_frontier_review_queue import DeploymentFrontierReviewQueue, build_deployment_frontier_review_queue
from .deployment_frontier_review_sla import DeploymentFrontierReviewSla, build_deployment_frontier_review_sla
from .deployment_frontier_runbook import DeploymentFrontierRunbook, build_deployment_frontier_runbook
from .deployment_frontier_schema import DeploymentFrontierSchema, default_deployment_frontier_schema
from .deployment_frontier_summary import DeploymentFrontierSummary, build_deployment_frontier_summary
from .deployment_frontier_support import deployment_address
from .deployment_frontier_thresholds import DeploymentFrontierThresholdReport, build_deployment_frontier_threshold_report
from .deployment_frontier_transcript import DeploymentFrontierTranscript, build_deployment_frontier_transcript
from .deployment_frontier_validation_matrix import DeploymentFrontierValidationMatrix, build_deployment_frontier_validation_matrix
from .deployment_frontier_views import DeploymentFrontierView, build_deployment_frontier_view
from .serialization import jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRuntimeStage:
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
class DeploymentFrontierRuntimeReport:
    run_id: str
    stages: tuple[DeploymentFrontierRuntimeStage, ...]
    fixture: DeploymentFrontierFixture
    audit: DeploymentFrontierDataAudit
    evaluation: Any
    metrics: DeploymentFrontierMetrics
    policy: DeploymentFrontierPolicy
    schema: DeploymentFrontierSchema
    lineage: DeploymentFrontierLineage
    reconciliation: DeploymentFrontierReconciliation
    quality: DeploymentFrontierQualityReport
    replay: DeploymentFrontierReplayReport
    release: DeploymentFrontierReleaseManifest
    artifacts: DeploymentFrontierArtifactInventory
    summary: DeploymentFrontierSummary
    view: DeploymentFrontierView
    queue: DeploymentFrontierReviewQueue
    sla: DeploymentFrontierReviewSla
    handoff: DeploymentFrontierHandoff
    integrity: DeploymentFrontierIntegrityReport
    depth: DeploymentFrontierDepthAudit
    operational: DeploymentFrontierOperationalMatrix
    performance: DeploymentFrontierPerformanceBudget
    assurance: DeploymentFrontierAssuranceSummary
    failure_injection: DeploymentFrontierFailureReport
    compliance: Any
    diagnostics: DeploymentFrontierDiagnostics
    plan: DeploymentFrontierExecutionPlan
    thresholds: DeploymentFrontierThresholdReport
    validation: DeploymentFrontierValidationMatrix
    access: Any
    compatibility: Any
    release_checks: DeploymentFrontierReleaseCheckReport
    runbook: DeploymentFrontierRunbook
    freshness: DeploymentFrontierFreshnessReport
    audit_log: DeploymentFrontierAuditLog
    transcript: DeploymentFrontierTranscript
    package: DeploymentFrontierPackageManifest
    bundle: DeploymentFrontierReleaseBundle
    trace: DeploymentFrontierTrace
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_deployment_frontier_runtime(
    fixture: DeploymentFrontierFixture | None = None,
    *,
    run_id: str = "deployment-frontier-runtime",
) -> DeploymentFrontierRuntimeReport:
    fixture = fixture or default_deployment_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[DeploymentFrontierRuntimeStage] = []

    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        duration = round((perf_counter() - started) * 1000, 3)
        address = getattr(result, "content_address", None) or deployment_address(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": duration, "output_address": address, "detail": detail}
        stages.append(DeploymentFrontierRuntimeStage(**body, content_address=deployment_address(body)))
        return result

    audit = stage("data-audit", lambda: audit_deployment_frontier_data(fixture), "audit public aggregate sources and records")
    adapters = stage("adapters", build_deployment_frontier_adapters, "load four operation adapters")
    schema = stage("schema", default_deployment_frontier_schema, "load typed operation fields")
    evaluation = stage("fixture-evaluation", lambda: evaluate_deployment_frontier_fixture(fixture), "execute positive and control rows")
    metrics = stage("metrics", lambda: measure_deployment_frontier(evaluation), "measure operation and issue distributions")
    policy = stage("policy", default_deployment_frontier_policy, "materialize research-use policy")
    lineage = stage("lineage", lambda: build_deployment_frontier_lineage(fixture, evaluation), "build source-to-execution graph")
    reconciliation = stage("reconciliation", lambda: reconcile_deployment_frontier(fixture, evaluation), "compare expected and observed states")
    quality = stage("quality-gate", lambda: run_deployment_frontier_quality_gate(audit, evaluation, adapters, schema, reconciliation), "run blocking quality checks")
    replay = stage("replay", lambda: replay_deployment_frontier_evaluation(fixture, evaluation), "replay addresses")
    release = stage("release", lambda: build_deployment_frontier_release(fixture, evaluation, quality, lineage, replay, release_id=run_id), "build release manifest")
    artifacts = stage("artifacts", lambda: build_deployment_frontier_artifact_inventory(fixture, release), "inventory content-addressed artifacts")
    view = stage("review-view", lambda: build_deployment_frontier_view(evaluation), "build stable review projection")
    queue = stage("review-queue", lambda: build_deployment_frontier_review_queue(evaluation), "route controls to bounded review")
    sla = stage("review-sla", lambda: build_deployment_frontier_review_sla(queue), "assign response bands")
    handoff = stage("handoff", lambda: build_deployment_frontier_handoff(fixture, evaluation, metrics, queue), "assemble review handoff")
    integrity = stage("integrity", lambda: evaluate_deployment_frontier_integrity(fixture, evaluation), "recompute nested addresses")
    depth = stage("depth", lambda: audit_deployment_frontier_depth(fixture, evaluation), "audit scenario and evidence planes")
    operational = stage("operational", lambda: build_deployment_frontier_operational_matrix(evaluation), "map outcomes to operations")
    performance = stage("performance", lambda: build_deployment_frontier_performance_budget(evaluation), "close local resource budget")
    assurance = stage("assurance", lambda: build_deployment_frontier_assurance_summary(quality, depth, integrity), "summarize assurance planes")
    failure_injection = stage("failure-injection", run_deployment_frontier_failure_injections, "rehearse all twelve controls")
    compliance = stage("compliance", lambda: evaluate_deployment_frontier_compliance(fixture), "audit public aggregate compliance")
    diagnostics = stage("diagnostics", lambda: diagnose_deployment_frontier(evaluation), "materialize issue findings")
    plan = stage("execution-plan", build_deployment_frontier_execution_plan, "build dependency-safe runtime plan")
    thresholds = stage("thresholds", build_deployment_frontier_threshold_report, "record gate boundaries")
    validation = stage("validation", lambda: build_deployment_frontier_validation_matrix(evaluation), "cover validation planes")
    access = stage("access", lambda: build_deployment_frontier_access_manifest(fixture), "describe public surfaces")
    compatibility = stage("compatibility", evaluate_deployment_frontier_compatibility, "check contract and runtime compatibility")
    release_checks = stage("release-checks", lambda: evaluate_deployment_frontier_release_checks(quality, integrity, compatibility), "independently check release gates")
    runbook = stage("runbook", build_deployment_frontier_runbook, "materialize executable runbook")
    freshness = stage("freshness", lambda: evaluate_deployment_frontier_freshness(fixture), "check source receipt freshness")
    audit_log = stage("audit-log", lambda: build_deployment_frontier_audit_log(tuple(item.stage_id for item in stages), run_id=run_id), "build append-only stage log")
    transcript = stage("transcript", lambda: build_deployment_frontier_transcript(tuple(item.stage_id for item in stages)), "render ordered stage transcript")
    summary = stage("summary", lambda: build_deployment_frontier_summary(evaluation, metrics, release), "build compact release summary")
    package = stage("package", lambda: build_deployment_frontier_package_manifest(release, artifacts), "build package manifest")
    bundle = stage("bundle", lambda: assemble_deployment_frontier_bundle(release, package, artifacts, summary), "assemble release bundle")
    trace = stage("observability", lambda: build_deployment_frontier_trace(run_id, tuple({"stage_id": item.stage_id, "state": item.state, "output_address": item.output_address, "events": (item.detail,)} for item in stages), accepted=quality.accepted), "emit ordered trace")
    accepted = bool(audit.accepted and evaluation.accepted and quality.accepted and replay.deterministic and release.accepted and artifacts.complete and handoff.accepted and integrity.accepted and depth.accepted and operational.accepted and performance.accepted and assurance.accepted and failure_injection.accepted and compliance.accepted and diagnostics.accepted and plan.accepted and thresholds.accepted and validation.accepted and access.accepted and compatibility.compatible and release_checks.passed and runbook.executable and freshness.accepted and audit_log.contiguous and transcript.accepted and package.complete and bundle.accepted and trace.accepted)
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "audit": audit, "evaluation": evaluation, "metrics": metrics, "policy": policy, "schema": schema, "lineage": lineage, "reconciliation": reconciliation, "quality": quality, "replay": replay, "release": release, "artifacts": artifacts, "summary": summary, "view": view, "queue": queue, "sla": sla, "handoff": handoff, "integrity": integrity, "depth": depth, "operational": operational, "performance": performance, "assurance": assurance, "failure_injection": failure_injection, "compliance": compliance, "diagnostics": diagnostics, "plan": plan, "thresholds": thresholds, "validation": validation, "access": access, "compatibility": compatibility, "release_checks": release_checks, "runbook": runbook, "freshness": freshness, "audit_log": audit_log, "transcript": transcript, "package": package, "bundle": bundle, "trace": trace, "accepted": accepted}
    return DeploymentFrontierRuntimeReport(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierRuntimeReport", "DeploymentFrontierRuntimeStage", "run_deployment_frontier_runtime"]
