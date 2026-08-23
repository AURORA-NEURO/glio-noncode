"""Ordered end-to-end runtime for the D13 C01-C04 validation-design frontier."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from .serialization import content_hash, jsonable
from .validation_design_frontier_access import ValidationDesignAccessManifest, build_validation_design_access_manifest
from .validation_design_frontier_adapters import ValidationDesignAdapterRegistry, build_validation_design_adapters
from .validation_design_frontier_artifacts import ValidationDesignArtifactInventory, build_validation_design_artifact_inventory
from .validation_design_frontier_common import receipt
from .validation_design_frontier_controls import ValidationDesignControlCoverage, build_validation_design_control_coverage
from .validation_design_frontier_depth import ValidationDesignDepthAudit, audit_validation_design_depth
from .validation_design_frontier_diagnostics import ValidationDesignDiagnostics, diagnose_validation_design
from .validation_design_frontier_evidence_matrix import ValidationDesignEvidenceMatrix, build_validation_design_evidence_matrix
from .validation_design_frontier_failure_injection import ValidationDesignFailureReport, run_validation_design_failure_injections
from .validation_design_frontier_fixture_eval import evaluate_validation_design_fixture
from .validation_design_frontier_handoff import ValidationDesignHandoff, build_validation_design_handoff
from .validation_design_frontier_integrity import ValidationDesignIntegrityReport, evaluate_validation_design_integrity
from .validation_design_frontier_lineage import ValidationDesignLineage, build_validation_design_lineage
from .validation_design_frontier_metrics import ValidationDesignMetrics, measure_validation_design
from .validation_design_frontier_policy import ValidationDesignPolicy, default_validation_design_policy
from .validation_design_frontier_public_data import ValidationDesignDataAudit, default_validation_design_frontier_fixture, audit_validation_design_frontier_data
from .validation_design_frontier_quality_gate import ValidationDesignQualityReport, run_validation_design_quality_gate
from .validation_design_frontier_reconciliation import ValidationDesignReconciliation, reconcile_validation_design
from .validation_design_frontier_replay import ValidationDesignReplayReport, replay_validation_design_evaluation
from .validation_design_frontier_review_queue import ValidationDesignReviewQueue, build_validation_design_review_queue
from .validation_design_frontier_schema import ValidationDesignSchema, default_validation_design_frontier_schema
from .validation_design_frontier_validation_matrix import ValidationDesignValidationMatrix, build_validation_design_validation_matrix
from .validation_design_frontier_views import ValidationDesignView, build_validation_design_view
from .validation_design_frontier_release import build_validation_design_release
from .validation_design_frontier_release_acceptance import build_validation_design_release_acceptance
from .validation_design_frontier_run_manifest import build_validation_design_run_manifest
from .validation_design_frontier_source_registry import build_validation_design_source_registry
from .validation_design_frontier_freshness import build_validation_design_freshness
from .validation_design_frontier_compatibility import build_validation_design_compatibility
from .validation_design_frontier_invariants import build_validation_design_invariants
from .validation_design_frontier_execution_plan import build_validation_design_execution_plan
from .validation_design_frontier_claim_boundary import build_validation_design_claim_boundary
from .validation_design_frontier_recovery import build_validation_design_recovery
from .validation_design_frontier_performance import build_validation_design_performance
from .validation_design_frontier_operational import build_validation_design_operational
from .validation_design_frontier_compliance import build_validation_design_compliance
from .validation_design_frontier_query import build_validation_design_query
from .validation_design_frontier_partitions import build_validation_design_partitions
from .validation_design_frontier_scenario_matrix import build_validation_design_scenario_matrix
from .validation_design_frontier_resources import build_validation_design_resources
from .validation_design_frontier_bundle import build_validation_design_bundle
from .validation_design_frontier_public_data_boundary import build_validation_design_public_data_boundary
from .validation_design_frontier_report import build_validation_design_report
from .validation_design_frontier_exports import build_validation_design_exports
from .validation_design_frontier_integrity_summary import build_validation_design_integrity_summary
from .validation_design_frontier_review_sla import build_validation_design_review_sla
from .validation_design_frontier_review_protocol import build_validation_design_review_protocol
from .validation_design_frontier_query_facets import build_validation_design_query_facets
from .validation_design_frontier_assurance import build_validation_design_assurance
from .validation_design_frontier_audit_log import build_validation_design_audit_log
from .validation_design_frontier_transcript import build_validation_design_transcript
from .validation_design_frontier_observability import build_validation_design_observability
from .validation_design_frontier_provenance import build_validation_design_provenance
from .validation_design_frontier_provenance_check import build_validation_design_provenance_check
from .validation_design_frontier_decision_ledger import build_validation_design_decision_ledger
from .validation_design_frontier_runbook import build_validation_design_runbook
from .validation_design_frontier_summary import build_validation_design_summary
from .validation_design_frontier_package_manifest import build_validation_design_package_manifest
from .validation_design_frontier_review_ledger import build_validation_design_review_ledger
from .validation_design_frontier_schema_diagnostics import build_validation_design_schema_diagnostics
from .validation_design_frontier_reproducibility import build_validation_design_reproducibility
from .validation_design_frontier_attestation import build_validation_design_attestation
from .validation_design_frontier_publication_policy import build_validation_design_publication_policy
from .validation_design_frontier_operator_console import build_validation_design_operator_console
from .validation_design_frontier_context_boundary import build_validation_design_context_boundary
from .validation_design_frontier_contract_migrations import build_validation_design_contract_migrations
from .validation_design_frontier_provenance_graph import build_validation_design_provenance_graph
from .validation_design_frontier_release_checks import build_validation_design_release_checks
from .validation_design_frontier_execution_ledger import build_validation_design_execution_ledger
from .validation_design_frontier_review_assignment import build_validation_design_review_assignment
from .validation_design_frontier_source_citations import build_validation_design_source_citations
from .validation_design_frontier_outcome_summary import build_validation_design_outcome_summary
from .validation_design_frontier_artifact_manifest import build_validation_design_artifact_manifest
from .validation_design_frontier_release_transcript import build_validation_design_release_transcript
from .validation_design_frontier_review_metrics import build_validation_design_review_metrics
from .validation_design_frontier_source_receipt_index import build_validation_design_source_receipt_index
from .validation_design_frontier_scenario_replay import build_validation_design_scenario_replay
from .validation_design_frontier_safety_projection import build_validation_design_safety_projection
from .validation_design_frontier_state_transition import build_validation_design_state_transition
from .validation_design_frontier_boundary_report import build_validation_design_boundary_report

@dataclass(frozen=True, slots=True)
class ValidationDesignRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    duration_ms: float
    output_address: str
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class ValidationDesignRuntimeReport:
    run_id: str
    stages: tuple[ValidationDesignRuntimeStage, ...]
    fixture: Any
    audit: ValidationDesignDataAudit
    adapters: ValidationDesignAdapterRegistry
    schema: ValidationDesignSchema
    evaluation: Any
    metrics: ValidationDesignMetrics
    policy: ValidationDesignPolicy
    lineage: ValidationDesignLineage
    reconciliation: ValidationDesignReconciliation
    quality: ValidationDesignQualityReport
    replay: ValidationDesignReplayReport
    view: ValidationDesignView
    queue: ValidationDesignReviewQueue
    handoff: ValidationDesignHandoff
    integrity: ValidationDesignIntegrityReport
    depth: ValidationDesignDepthAudit
    controls: ValidationDesignControlCoverage
    validation: ValidationDesignValidationMatrix
    evidence: ValidationDesignEvidenceMatrix
    access: ValidationDesignAccessManifest
    failure_injection: ValidationDesignFailureReport
    diagnostics: ValidationDesignDiagnostics
    planes: dict[str, Any]
    accepted: bool
    content_address: str
    @property
    def stage_ids(self) -> tuple[str, ...]: return tuple(item.stage_id for item in self.stages)
    def to_dict(self) -> dict[str, Any]: return jsonable(self) | {"stage_ids": list(self.stage_ids)}

def run_validation_design_runtime(fixture: Any | None = None, *, run_id: str = "validation-design-runtime") -> ValidationDesignRuntimeReport:
    fixture = fixture or default_validation_design_frontier_fixture()
    stages: list[ValidationDesignRuntimeStage] = []
    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter(); result = fn(); elapsed = round((perf_counter() - started) * 1000, 3)
        output_address = getattr(result, "content_address", None) or content_hash(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": elapsed, "output_address": output_address, "detail": detail}
        stages.append(ValidationDesignRuntimeStage(**body, content_address=content_hash(body))); return result

    audit = stage("data-audit", lambda: audit_validation_design_frontier_data(fixture), "audit public source receipts and scenario rows")
    adapters = stage("adapters", build_validation_design_adapters, "materialize four typed operation adapters")
    schema = stage("schema", default_validation_design_frontier_schema, "materialize required fields and output fields")
    evaluation = stage("fixture-evaluation", lambda: evaluate_validation_design_fixture(fixture), "execute positive and control scenarios")
    metrics = stage("metrics", lambda: measure_validation_design(evaluation), "measure states operations and issue codes")
    policy = stage("policy", default_validation_design_policy, "apply research-use wording boundary")
    lineage = stage("lineage", lambda: build_validation_design_lineage(fixture, evaluation), "join sources records and executions")
    reconciliation = stage("reconciliation", lambda: reconcile_validation_design(fixture, evaluation), "compare expected and observed outcomes")
    quality = stage("quality-gate", lambda: run_validation_design_quality_gate(audit, evaluation, adapters, schema, reconciliation), "run blocking quality checks")
    replay = stage("replay", lambda: replay_validation_design_evaluation(fixture, evaluation), "replay exact public scenario")
    view = stage("review-view", lambda: build_validation_design_view(evaluation), "build stable review rows")
    queue = stage("review-queue", lambda: build_validation_design_review_queue(evaluation), "route held rows with priority")
    handoff = stage("handoff", lambda: build_validation_design_handoff(fixture, evaluation, metrics, queue), "assemble bounded reviewer handoff")
    integrity = stage("integrity", lambda: evaluate_validation_design_integrity(fixture, evaluation), "recompute identity and address closure")
    depth = stage("depth", lambda: audit_validation_design_depth(fixture, evaluation), "assert four planes and eighty row checks")
    controls = stage("control-coverage", lambda: build_validation_design_control_coverage(evaluation), "verify three controls per capability")
    validation = stage("validation-matrix", lambda: build_validation_design_validation_matrix(evaluation), "close state issue role integrity safety")
    evidence = stage("evidence-matrix", lambda: build_validation_design_evidence_matrix(fixture, evaluation), "close public source joins")
    access = stage("access", lambda: build_validation_design_access_manifest(fixture), "describe public aggregate boundary")
    failure_injection = stage("failure-injection", run_validation_design_failure_injections, "rehearse malformed operation payloads")
    diagnostics = stage("diagnostics", lambda: diagnose_validation_design(evaluation), "assign issue severity and action")
    artifacts = stage("artifacts", lambda: build_validation_design_artifact_inventory(fixture, evaluation, run_id), "inventory content-addressed artifacts")
    release = stage("release", lambda: build_validation_design_release(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, run_id=run_id), "build release receipt")
    release_acceptance = stage("release-acceptance", lambda: build_validation_design_release_acceptance(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access), "apply independent release gate")
    source_registry = stage("source-registry", lambda: build_validation_design_source_registry(fixture=fixture), "register public receipts")
    freshness = stage("freshness", lambda: build_validation_design_freshness(fixture=fixture), "check declared receipt versions")
    compatibility = stage("compatibility", lambda: build_validation_design_compatibility(adapters=adapters, schema=schema), "check adapter and schema compatibility")
    invariants = stage("invariants", lambda: build_validation_design_invariants(fixture=fixture, evaluation=evaluation), "audit cross-plane invariants")
    execution_plan = stage("execution-plan", lambda: build_validation_design_execution_plan(steps=tuple(item.stage_id for item in stages)), "materialize dependency order")
    claim_boundary = stage("claim-boundary", lambda: build_validation_design_claim_boundary(fixture=fixture), "enforce research interpretation")
    recovery = stage("recovery", lambda: build_validation_design_recovery(evaluation=evaluation), "map outcomes to safe actions")
    performance = stage("performance", lambda: build_validation_design_performance(evaluation=evaluation), "close local resource budget")
    operational = stage("operational", lambda: build_validation_design_operational(evaluation=evaluation, run_id=run_id), "map outcomes to operations")
    compliance = stage("compliance", lambda: build_validation_design_compliance(fixture=fixture), "audit aggregate compliance")
    query = stage("query", lambda: build_validation_design_query(evaluation=evaluation), "exercise deterministic query projection")
    partitions = stage("partitions", lambda: build_validation_design_partitions(evaluation=evaluation), "partition rows by operation and state")
    scenario = stage("scenario-matrix", lambda: build_validation_design_scenario_matrix(evaluation=evaluation), "reconcile positive and control cells")
    resources = stage("resource-accounting", lambda: build_validation_design_resources(evaluation=evaluation, fixture=fixture), "account bounded resources")
    public_boundary = stage("public-boundary", lambda: build_validation_design_public_data_boundary(fixture=fixture), "reconfirm public aggregate boundary")
    report = stage("report", lambda: build_validation_design_report(evaluation=evaluation, run_id=run_id), "render stable summary values")
    exports = stage("exports", lambda: build_validation_design_exports(evaluation=evaluation), "prepare review export contract")
    integrity_summary = stage("integrity-summary", lambda: build_validation_design_integrity_summary(fixture=fixture, evaluation=evaluation), "summarize address closure")
    review_sla = stage("review-sla", lambda: build_validation_design_review_sla(evaluation=evaluation), "assign response bands")
    review_protocol = stage("review-protocol", lambda: build_validation_design_review_protocol(evaluation=evaluation), "materialize repeatable review steps")
    query_facets = stage("query-facets", lambda: build_validation_design_query_facets(evaluation=evaluation), "materialize stable query facets")
    assurance = stage("assurance", lambda: build_validation_design_assurance(evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, evidence=evidence, validation=validation, access=access), "aggregate assurance decisions")
    provenance = stage("provenance", lambda: build_validation_design_provenance(fixture=fixture, evaluation=evaluation), "build source and evaluation provenance")
    provenance_check = stage("provenance-check", lambda: build_validation_design_provenance_check(fixture=fixture, evaluation=evaluation), "verify provenance addresses")
    decision_ledger = stage("decision-ledger", lambda: build_validation_design_decision_ledger(evaluation=evaluation), "append planning decisions")
    runbook = stage("runbook", lambda: build_validation_design_runbook(run_id=run_id), "materialize repeatable runbook")
    summary = stage("summary", lambda: build_validation_design_summary(evaluation=evaluation), "summarize outcome counts")
    package_manifest = stage("package-manifest", lambda: build_validation_design_package_manifest(fixture=fixture, evaluation=evaluation), "describe operation packages")
    review_ledger = stage("review-ledger", lambda: build_validation_design_review_ledger(evaluation=evaluation), "record held-row reasons")
    schema_diagnostics = stage("schema-diagnostics", lambda: build_validation_design_schema_diagnostics(schema=schema), "diagnose schema coverage")
    reproducibility = stage("reproducibility", lambda: build_validation_design_reproducibility(fixture=fixture, evaluation=evaluation), "close exact replay packet")
    attestation = stage("attestation", lambda: build_validation_design_attestation(fixture=fixture, evaluation=evaluation), "attest public aggregate inputs")
    publication_policy = stage("publication-policy", lambda: build_validation_design_publication_policy(fixture=fixture), "apply aggregate publication policy")
    operator_console = stage("operator-console", lambda: build_validation_design_operator_console(evaluation=evaluation, run_id=run_id), "assemble held-work console")
    context_boundary = stage("context-boundary", lambda: build_validation_design_context_boundary(fixture=fixture), "verify exact context partition")
    contract_migrations = stage("contract-migrations", lambda: build_validation_design_contract_migrations(fixture=fixture), "check contract version compatibility")
    provenance_graph = stage("provenance-graph", lambda: build_validation_design_provenance_graph(fixture=fixture, evaluation=evaluation), "summarize provenance graph")
    release_checks = stage("release-checks", lambda: build_validation_design_release_checks(audit=audit, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth), "run independent release checks")
    execution_ledger = stage("execution-ledger", lambda: build_validation_design_execution_ledger(stages=stages), "record ordered execution ledger")
    review_assignment = stage("review-assignment", lambda: build_validation_design_review_assignment(evaluation=evaluation), "assign issue-bearing rows")
    source_citations = stage("source-citations", lambda: build_validation_design_source_citations(fixture=fixture), "summarize public source citations")
    outcome_summary = stage("outcome-summary", lambda: build_validation_design_outcome_summary(evaluation=evaluation), "close release outcome summary")
    artifact_manifest = stage("artifact-manifest", lambda: build_validation_design_artifact_manifest(fixture=fixture, evaluation=evaluation), "index core release artifacts")
    release_transcript = stage("release-transcript", lambda: build_validation_design_release_transcript(run_id=run_id), "record release events")
    review_metrics = stage("review-metrics", lambda: build_validation_design_review_metrics(evaluation=evaluation), "measure reviewer workload")
    source_receipt_index = stage("source-receipt-index", lambda: build_validation_design_source_receipt_index(fixture=fixture), "index source receipts")
    scenario_replay = stage("scenario-replay", lambda: build_validation_design_scenario_replay(evaluation=evaluation), "replay scenario partitions")
    safety_projection = stage("safety-projection", lambda: build_validation_design_safety_projection(evaluation=evaluation), "audit safe execution projections")
    state_transition = stage("state-transition", lambda: build_validation_design_state_transition(evaluation=evaluation), "audit allowed outcome states")
    boundary_report = stage("boundary-report", lambda: build_validation_design_boundary_report(fixture=fixture), "close interpretation boundary")
    bundle = stage("bundle", lambda: build_validation_design_bundle(fixture=fixture, evaluation=evaluation, artifacts=artifacts, release=release), "assemble release bundle")
    run_manifest = stage("run-manifest", lambda: build_validation_design_run_manifest(run_id=run_id, fixture=fixture, stages=stages), "record run and stage identities")
    audit_log = stage("audit-log", lambda: build_validation_design_audit_log(run_id=run_id, stages=stages), "build append-only stage log")
    transcript = stage("transcript", lambda: build_validation_design_transcript(run_id=run_id, stages=stages), "render ordered transcript")
    observability = stage("observability", lambda: build_validation_design_observability(run_id=run_id, stages=stages, evaluation=evaluation), "emit structured runtime trace")
    planes = {"release": release, "release_acceptance": release_acceptance, "source_registry": source_registry, "freshness": freshness, "compatibility": compatibility, "invariants": invariants, "execution_plan": execution_plan, "claim_boundary": claim_boundary, "recovery": recovery, "performance": performance, "operational": operational, "compliance": compliance, "query": query, "partitions": partitions, "scenario": scenario, "resources": resources, "public_boundary": public_boundary, "report": report, "exports": exports, "integrity_summary": integrity_summary, "review_sla": review_sla, "review_protocol": review_protocol, "query_facets": query_facets, "assurance": assurance, "provenance": provenance, "provenance_check": provenance_check, "decision_ledger": decision_ledger, "runbook": runbook, "summary": summary, "package_manifest": package_manifest, "review_ledger": review_ledger, "schema_diagnostics": schema_diagnostics, "reproducibility": reproducibility, "attestation": attestation, "publication_policy": publication_policy, "operator_console": operator_console, "context_boundary": context_boundary, "contract_migrations": contract_migrations, "provenance_graph": provenance_graph, "release_checks": release_checks, "execution_ledger": execution_ledger, "review_assignment": review_assignment, "source_citations": source_citations, "outcome_summary": outcome_summary, "artifact_manifest": artifact_manifest, "release_transcript": release_transcript, "review_metrics": review_metrics, "source_receipt_index": source_receipt_index, "scenario_replay": scenario_replay, "safety_projection": safety_projection, "state_transition": state_transition, "boundary_report": boundary_report, "bundle": bundle, "run_manifest": run_manifest, "audit_log": audit_log, "transcript": transcript, "observability": observability}
    accepted = all((audit.accepted, evaluation.accepted, quality.accepted, lineage.closed, reconciliation.accepted, replay.deterministic, view.accepted, queue.accepted, handoff.accepted, integrity.accepted, depth.accepted, controls.accepted, validation.accepted, evidence.accepted, access.content_address.startswith("sha256:"), failure_injection.accepted, artifacts.complete, all(getattr(value, "accepted", False) for value in planes.values())))
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "audit": audit, "adapters": adapters, "schema": schema, "evaluation": evaluation, "metrics": metrics, "policy": policy, "lineage": lineage, "reconciliation": reconciliation, "quality": quality, "replay": replay, "view": view, "queue": queue, "handoff": handoff, "integrity": integrity, "depth": depth, "controls": controls, "validation": validation, "evidence": evidence, "access": access, "failure_injection": failure_injection, "diagnostics": diagnostics, "planes": planes, "accepted": accepted}
    return ValidationDesignRuntimeReport(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignRuntimeReport", "ValidationDesignRuntimeStage", "run_validation_design_runtime"]
