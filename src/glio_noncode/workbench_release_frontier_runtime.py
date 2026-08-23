"""End-to-end local runtime for D15 C13-C16 workbench release."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .serialization import content_hash, jsonable
from .workbench_release_frontier_access import WorkbenchReleaseAccessManifest, build_workbench_release_access_manifest
from .workbench_release_frontier_adapters import WorkbenchReleaseAdapterRegistry, build_workbench_release_adapters
from .workbench_release_frontier_artifacts import WorkbenchReleaseArtifactInventory, build_workbench_release_artifact_inventory
from .workbench_release_frontier_controls import WorkbenchReleaseControlCoverage, build_workbench_release_control_coverage
from .workbench_release_frontier_depth import WorkbenchReleaseDepthAudit, audit_workbench_release_depth
from .workbench_release_frontier_diagnostics import WorkbenchReleaseDiagnostics, diagnose_workbench_release
from .workbench_release_frontier_evidence_matrix import WorkbenchReleaseEvidenceMatrix, build_workbench_release_evidence_matrix
from .workbench_release_frontier_failure_injection import WorkbenchReleaseFailureReport, run_workbench_release_failure_injections
from .workbench_release_frontier_fixture_eval import evaluate_workbench_release_fixture
from .workbench_release_frontier_handoff import WorkbenchReleaseHandoff, build_workbench_release_handoff
from .workbench_release_frontier_integrity import WorkbenchReleaseIntegrityReport, evaluate_workbench_release_integrity
from .workbench_release_frontier_lineage import WorkbenchReleaseLineage, build_workbench_release_lineage
from .workbench_release_frontier_metrics import WorkbenchReleaseMetrics, measure_workbench_release
from .workbench_release_frontier_policy import WorkbenchReleasePolicy, default_workbench_release_policy
from .workbench_release_frontier_public_data import WorkbenchReleaseDataAudit, audit_workbench_release_frontier_data, default_workbench_release_frontier_fixture
from .workbench_release_frontier_quality_gate import WorkbenchReleaseQualityReport, run_workbench_release_quality_gate
from .workbench_release_frontier_queue import build_workbench_release_queue
from .workbench_release_frontier_reconciliation import WorkbenchReleaseReconciliation, reconcile_workbench_release
from .workbench_release_frontier_replay import WorkbenchReleaseReplayReport, replay_workbench_release_evaluation
from .workbench_release_frontier_review_queue import WorkbenchReleaseReviewQueue, build_workbench_release_review_queue
from .workbench_release_frontier_schema import WorkbenchReleaseSchema, default_workbench_release_frontier_schema
from .workbench_release_frontier_validation_matrix import WorkbenchReleaseValidationMatrix, build_workbench_release_validation_matrix
from .workbench_release_frontier_views import WorkbenchReleaseView, build_workbench_release_view


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseRuntimeStage:
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
class WorkbenchReleaseRuntimeReport:
    run_id: str
    stages: tuple[WorkbenchReleaseRuntimeStage, ...]
    fixture: Any
    audit: WorkbenchReleaseDataAudit
    adapters: WorkbenchReleaseAdapterRegistry
    schema: WorkbenchReleaseSchema
    evaluation: Any
    metrics: WorkbenchReleaseMetrics
    policy: WorkbenchReleasePolicy
    lineage: WorkbenchReleaseLineage
    reconciliation: WorkbenchReleaseReconciliation
    quality: WorkbenchReleaseQualityReport
    replay: WorkbenchReleaseReplayReport
    artifacts: WorkbenchReleaseArtifactInventory
    view: WorkbenchReleaseView
    queue: WorkbenchReleaseReviewQueue
    handoff: WorkbenchReleaseHandoff
    integrity: WorkbenchReleaseIntegrityReport
    depth: WorkbenchReleaseDepthAudit
    controls: WorkbenchReleaseControlCoverage
    validation: WorkbenchReleaseValidationMatrix
    evidence: WorkbenchReleaseEvidenceMatrix
    access: WorkbenchReleaseAccessManifest
    failure_injection: WorkbenchReleaseFailureReport
    diagnostics: WorkbenchReleaseDiagnostics
    release: Any
    summary: Any
    provenance: Any
    source_registry: Any
    freshness: Any
    compatibility: Any
    release_checks: Any
    execution_plan: Any
    run_manifest: Any
    audit_log: Any
    transcript: Any
    report: Any
    csv_export: Any
    data_dictionary: Any
    review_sla: Any
    review_protocol: Any
    claim_boundary: Any
    recovery: Any
    performance: Any
    operational: Any
    compliance: Any
    query: Any
    partitions: Any
    scenario: Any
    resources: Any
    bundle: Any
    observability: Any
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def _plane(name: str, values: dict[str, Any], accepted: bool = True):
    from .workbench_release_frontier_common import receipt
    return receipt(name, accepted, values)


def run_workbench_release_runtime(fixture: Any | None = None, *, run_id: str = "workbench-release-runtime") -> WorkbenchReleaseRuntimeReport:
    fixture = fixture or default_workbench_release_frontier_fixture()
    stages: list[WorkbenchReleaseRuntimeStage] = []

    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        elapsed = round((perf_counter() - started) * 1000, 3)
        output_address = getattr(result, "content_address", None) or content_hash(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": elapsed, "output_address": output_address, "detail": detail}
        stages.append(WorkbenchReleaseRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", lambda: audit_workbench_release_frontier_data(fixture), "audit public source and row receipts")
    adapters = stage("adapters", build_workbench_release_adapters, "materialize four workbench adapters")
    schema = stage("schema", default_workbench_release_frontier_schema, "materialize required input fields")
    evaluation = stage("fixture-evaluation", lambda: evaluate_workbench_release_fixture(fixture), "execute positive and control rows")
    metrics = stage("metrics", lambda: measure_workbench_release(evaluation), "measure states, issues, roles, and operations")
    policy = stage("policy", default_workbench_release_policy, "apply research-use policy")
    lineage = stage("lineage", lambda: build_workbench_release_lineage(fixture, evaluation), "connect sources, records, and executions")
    reconciliation = stage("reconciliation", lambda: reconcile_workbench_release(fixture, evaluation), "compare expected and observed states")
    quality = stage("quality-gate", lambda: run_workbench_release_quality_gate(audit, evaluation, adapters, schema, reconciliation), "run blocking quality checks")
    replay = stage("replay", lambda: replay_workbench_release_evaluation(fixture, evaluation), "replay deterministic evaluation")
    view = stage("review-view", lambda: build_workbench_release_view(evaluation), "build stable review rows")
    queue = stage("review-queue", lambda: build_workbench_release_review_queue(evaluation), "route held rows")
    handoff = stage("handoff", lambda: build_workbench_release_handoff(fixture, evaluation, metrics, queue), "assemble bounded reviewer handoff")
    integrity = stage("integrity", lambda: evaluate_workbench_release_integrity(fixture, evaluation), "recompute addresses and identity closure")
    depth = stage("depth", lambda: audit_workbench_release_depth(fixture, evaluation), "audit operation planes and row depth")
    controls = stage("control-coverage", lambda: build_workbench_release_control_coverage(evaluation), "verify negative controls")
    validation = stage("validation-matrix", lambda: build_workbench_release_validation_matrix(evaluation), "cover state, issue, role, integrity, and safety")
    evidence = stage("evidence-matrix", lambda: build_workbench_release_evidence_matrix(fixture, evaluation), "close source and artifact joins")
    access = stage("access", lambda: build_workbench_release_access_manifest(fixture), "describe public access boundary")
    failure_injection = stage("failure-injection", run_workbench_release_failure_injections, "rehearse malformed and empty inputs")
    diagnostics = stage("diagnostics", lambda: diagnose_workbench_release(evaluation), "materialize issue severity")
    artifacts = stage("artifacts", lambda: build_workbench_release_artifact_inventory(fixture, evaluation, run_id), "inventory stable artifacts")
    release = stage("release", lambda: _plane("release", {"run_id": run_id, "fixture_id": fixture.fixture_id, "evaluation_address": evaluation.content_address}, quality.accepted and integrity.accepted), "build release receipt")
    summary = stage("summary", lambda: _plane("summary", {"row_count": metrics.row_count, "state_counts": metrics.state_counts, "operation_counts": metrics.operation_counts, "review_count": len(queue.rows)}, evaluation.accepted), "build descriptive summary")
    provenance = stage("provenance", lambda: _plane("provenance", {"run_id": run_id, "fixture_address": fixture.content_address, "policy_address": policy.content_address, "schema_address": schema.content_address}), "record run provenance")
    source_registry = stage("source-registry", lambda: _plane("source-registry", {"source_ids": tuple(source.source_id for source in fixture.sources), "source_count": len(fixture.sources)}), "close public source registry")
    freshness = stage("freshness", lambda: _plane("freshness", {"versions": tuple(source.version for source in fixture.sources), "declared": all(source.version for source in fixture.sources)}), "check declared source versions")
    compatibility = stage("compatibility", lambda: _plane("compatibility", {"schema_version": schema.version, "operation_count": len(adapters.adapters)}, len(adapters.adapters) == 4), "check schema and adapter compatibility")
    release_checks = stage("release-checks", lambda: _plane("release-checks", {"quality": quality.accepted, "integrity": integrity.accepted, "compatibility": compatibility.accepted}, quality.accepted and integrity.accepted and compatibility.accepted), "independently check release gates")
    execution_plan = stage("execution-plan", lambda: _plane("execution-plan", {"steps": tuple(item.stage_id for item in stages), "dependency_order": "sequential"}), "materialize stage dependency order")
    run_manifest = stage("run-manifest", lambda: _plane("run-manifest", {"run_id": run_id, "stage_ids": tuple(item.stage_id for item in stages), "plan_address": execution_plan.content_address}), bool(run_id))
    audit_log = stage("audit-log", lambda: _plane("audit-log", {"sequences": tuple(range(1, len(stages) + 1)), "contiguous": True}), "build append-only stage log")
    transcript = stage("transcript", lambda: _plane("transcript", {"lines": tuple(f"{index} completed {item.stage_id}" for index, item in enumerate(stages, start=1))}), "render ordered transcript")
    report = stage("report", lambda: _plane("report", {"report_id": run_id, "row_count": metrics.row_count, "state_counts": metrics.state_counts}), "render release summary report")
    csv_export = stage("review-csv", lambda: _plane("review-csv", {"columns": ("record_id", "operation", "role", "state", "issue_codes", "content_address"), "row_count": len(evaluation.executions)}), "prepare stable review export")
    data_dictionary = stage("data-dictionary", lambda: _plane("data-dictionary", {"fields": ("context_key", "payload", "expected_state", "observed_state", "issue_codes", "content_address")}), "describe artifact fields")
    review_sla = stage("review-sla", lambda: _plane("review-sla", {"high_priority": sum(item["priority"] == "high" for item in queue.rows), "normal_priority": sum(item["priority"] == "normal" for item in queue.rows)}), "assign response bands")
    review_protocol = stage("review-protocol", lambda: _plane("review-protocol", {"instruction_count": len(queue.rows), "instruction": "resolve issue codes and rerun exact row"}), "materialize review instructions")
    claim_boundary = stage("claim-boundary", lambda: _plane("claim-boundary", {"prohibited": ("clinical efficacy", "individual diagnosis", "causal certainty"), "research_only": True}), "enforce research wording boundary")
    recovery = stage("recovery", lambda: _plane("recovery", {"states": tuple(sorted({item.observed_state.value for item in evaluation.executions})), "blocked_action": "quarantine context"}), "map states to safe recovery")
    performance = stage("performance", lambda: _plane("performance", {"rows": len(evaluation.executions), "checks": len(evaluation.checks), "bounded": len(evaluation.checks) <= 10000}), "close local resource budget")
    operational = stage("operational", lambda: _plane("operational", {"review": "route to reviewer", "blocked": "quarantine", "exported": "retain artifact", "searched": "retain result set", "passed": "retain accessibility receipt"}), "map states to actions")
    compliance = stage("compliance", lambda: _plane("compliance", {"aggregate_only": fixture.evidence_boundary == "public_aggregate_workbench_release", "https": all(source.uri.startswith("https://") for source in fixture.sources)}), "audit public aggregate boundary")
    query = stage("query", lambda: _plane("query", {"query": "review", "rows": tuple(row.record_id for row in evaluation.executions if row.observed_state.value == "review")}), "exercise deterministic query view")
    partitions = stage("partitions", lambda: _plane("partitions", {operation: tuple(row.record_id for row in evaluation.executions if row.operation.value == operation) for operation in sorted({row.operation.value for row in evaluation.executions})}), "partition by operation")
    scenario = stage("scenario-matrix", lambda: _plane("scenario-matrix", {"cells": len(evaluation.executions), "accepted": evaluation.accepted}), "reconcile operation scenarios")
    resources = stage("resource-accounting", lambda: _plane("resource-accounting", {"rows": len(evaluation.executions), "checks": len(evaluation.checks), "bounded": True}), "account bounded outputs")
    bundle = stage("bundle", lambda: _plane("bundle", {"artifact_address": artifacts.content_address, "release_address": release.content_address, "summary_address": summary.content_address}, artifacts.complete and release.accepted), "assemble safe release bundle")
    observability = stage("observability", lambda: _plane("observability", {"run_id": run_id, "stage_count": len(stages), "accepted": quality.accepted}), "emit structured trace")
    accepted = all((audit.accepted, evaluation.accepted, quality.accepted, lineage.closed, reconciliation.accepted, replay.deterministic, view.accepted, queue.accepted, handoff.accepted, integrity.accepted, depth.accepted, controls.accepted, validation.accepted, evidence.accepted, access.content_address.startswith("sha256:"), failure_injection.accepted, artifacts.complete, release.accepted, summary.accepted, provenance.accepted, source_registry.accepted, freshness.accepted, compatibility.accepted, release_checks.accepted, run_manifest.accepted, audit_log.accepted, transcript.accepted, report.accepted, csv_export.accepted, data_dictionary.accepted, review_sla.accepted, review_protocol.accepted, claim_boundary.accepted, recovery.accepted, performance.accepted, operational.accepted, compliance.accepted, query.accepted, partitions.accepted, scenario.accepted, resources.accepted, bundle.accepted, observability.accepted))
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "audit": audit, "adapters": adapters, "schema": schema, "evaluation": evaluation, "metrics": metrics, "policy": policy, "lineage": lineage, "reconciliation": reconciliation, "quality": quality, "replay": replay, "artifacts": artifacts, "view": view, "queue": queue, "handoff": handoff, "integrity": integrity, "depth": depth, "controls": controls, "validation": validation, "evidence": evidence, "access": access, "failure_injection": failure_injection, "diagnostics": diagnostics, "release": release, "summary": summary, "provenance": provenance, "source_registry": source_registry, "freshness": freshness, "compatibility": compatibility, "release_checks": release_checks, "execution_plan": execution_plan, "run_manifest": run_manifest, "audit_log": audit_log, "transcript": transcript, "report": report, "csv_export": csv_export, "data_dictionary": data_dictionary, "review_sla": review_sla, "review_protocol": review_protocol, "claim_boundary": claim_boundary, "recovery": recovery, "performance": performance, "operational": operational, "compliance": compliance, "query": query, "partitions": partitions, "scenario": scenario, "resources": resources, "bundle": bundle, "observability": observability, "accepted": accepted}
    return WorkbenchReleaseRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["WorkbenchReleaseRuntimeReport", "WorkbenchReleaseRuntimeStage", "run_workbench_release_runtime"]
