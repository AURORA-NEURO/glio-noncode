"""Ordered runtime for the D13 C05-C08 editing-design frontier."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from .serialization import content_hash, jsonable
from .editing_design_frontier_access import build_editing_design_access
from .editing_design_frontier_adapters import EditingDesignAdapterRegistry, build_editing_design_adapters
from .editing_design_frontier_contracts import EditingDesignFixture
from .editing_design_frontier_depth import build_editing_design_depth
from .editing_design_frontier_fixture_eval import evaluate_editing_design_fixture
from .editing_design_frontier_metrics import EditingDesignMetrics, measure_editing_design
from .editing_design_frontier_public_data import EditingDesignDataAudit, audit_editing_design_frontier_data, default_editing_design_frontier_fixture
from .editing_design_frontier_schema import EditingDesignSchema, default_editing_design_frontier_schema
from .editing_design_frontier_quality_gate import build_editing_design_quality_gate
from .editing_design_frontier_provenance import build_editing_design_provenance
from .editing_design_frontier_lineage import build_editing_design_lineage
from .editing_design_frontier_reconciliation import build_editing_design_reconciliation
from .editing_design_frontier_policy import build_editing_design_policy
from .editing_design_frontier_quality_gate import build_editing_design_quality_gate
from .editing_design_frontier_replay import build_editing_design_replay
from .editing_design_frontier_views import build_editing_design_views
from .editing_design_frontier_review_queue import build_editing_design_review_queue
from .editing_design_frontier_handoff import build_editing_design_handoff
from .editing_design_frontier_integrity import build_editing_design_integrity
from .editing_design_frontier_depth import build_editing_design_depth
from .editing_design_frontier_controls import build_editing_design_controls
from .editing_design_frontier_validation_matrix import build_editing_design_validation_matrix
from .editing_design_frontier_evidence_matrix import build_editing_design_evidence_matrix
from .editing_design_frontier_access import build_editing_design_access
from .editing_design_frontier_failure_injection import build_editing_design_failure_injection
from .editing_design_frontier_diagnostics import build_editing_design_diagnostics
from .editing_design_frontier_artifacts import build_editing_design_artifacts
from .editing_design_frontier_release import build_editing_design_release
from .editing_design_frontier_release_acceptance import build_editing_design_release_acceptance
from .editing_design_frontier_run_manifest import build_editing_design_run_manifest
from .editing_design_frontier_source_registry import build_editing_design_source_registry
from .editing_design_frontier_freshness import build_editing_design_freshness
from .editing_design_frontier_compatibility import build_editing_design_compatibility
from .editing_design_frontier_invariants import build_editing_design_invariants
from .editing_design_frontier_execution_plan import build_editing_design_execution_plan
from .editing_design_frontier_observability import build_editing_design_observability
from .editing_design_frontier_audit_log import build_editing_design_audit_log
from .editing_design_frontier_transcript import build_editing_design_transcript
from .editing_design_frontier_report import build_editing_design_report
from .editing_design_frontier_exports import build_editing_design_exports
from .editing_design_frontier_data_dictionary import build_editing_design_data_dictionary
from .editing_design_frontier_claim_boundary import build_editing_design_claim_boundary
from .editing_design_frontier_recovery import build_editing_design_recovery
from .editing_design_frontier_performance import build_editing_design_performance
from .editing_design_frontier_operational import build_editing_design_operational
from .editing_design_frontier_compliance import build_editing_design_compliance
from .editing_design_frontier_query import build_editing_design_query
from .editing_design_frontier_partitions import build_editing_design_partitions
from .editing_design_frontier_scenario_matrix import build_editing_design_scenario_matrix
from .editing_design_frontier_resources import build_editing_design_resources
from .editing_design_frontier_bundle import build_editing_design_bundle
from .editing_design_frontier_public_data_boundary import build_editing_design_public_data_boundary
from .editing_design_frontier_assurance import build_editing_design_assurance
from .editing_design_frontier_provenance_graph import build_editing_design_provenance_graph
from .editing_design_frontier_decision_ledger import build_editing_design_decision_ledger
from .editing_design_frontier_review_assignment import build_editing_design_review_assignment
from .editing_design_frontier_schema_diagnostics import build_editing_design_schema_diagnostics
from .editing_design_frontier_context_boundary import build_editing_design_context_boundary
from .editing_design_frontier_source_receipt_index import build_editing_design_source_receipt_index
from .editing_design_frontier_review_metrics import build_editing_design_review_metrics
from .editing_design_frontier_review_sla import build_editing_design_review_sla
from .editing_design_frontier_review_protocol import build_editing_design_review_protocol
from .editing_design_frontier_provenance_check import build_editing_design_provenance_check
from .editing_design_frontier_reproducibility import build_editing_design_reproducibility
from .editing_design_frontier_attestation import build_editing_design_attestation
from .editing_design_frontier_publication_policy import build_editing_design_publication_policy
from .editing_design_frontier_operator_console import build_editing_design_operator_console
from .editing_design_frontier_contract_migrations import build_editing_design_contract_migrations
from .editing_design_frontier_package_manifest import build_editing_design_package_manifest
from .editing_design_frontier_source_citations import build_editing_design_source_citations
from .editing_design_frontier_outcome_summary import build_editing_design_outcome_summary
from .editing_design_frontier_artifact_manifest import build_editing_design_artifact_manifest
from .editing_design_frontier_release_transcript import build_editing_design_release_transcript
from .editing_design_frontier_scenario_replay import build_editing_design_scenario_replay
from .editing_design_frontier_safety_projection import build_editing_design_safety_projection
from .editing_design_frontier_state_transition import build_editing_design_state_transition
from .editing_design_frontier_boundary_report import build_editing_design_boundary_report
from .editing_design_frontier_runbook import build_editing_design_runbook
from .editing_design_frontier_summary import build_editing_design_summary

@dataclass(frozen=True, slots=True)
class EditingDesignRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    duration_ms: float
    output_address: str
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

@dataclass(frozen=True, slots=True)
class EditingDesignRuntimeReport:
    run_id: str
    stages: tuple[EditingDesignRuntimeStage, ...]
    fixture: EditingDesignFixture
    audit: EditingDesignDataAudit
    adapters: EditingDesignAdapterRegistry
    schema: EditingDesignSchema
    evaluation: Any
    metrics: EditingDesignMetrics
    planes: dict[str, Any]
    accepted: bool
    content_address: str
    @property
    def stage_ids(self) -> tuple[str, ...]: return tuple(item.stage_id for item in self.stages)
    def to_dict(self) -> dict[str, Any]: return jsonable(self) | {"stage_ids": list(self.stage_ids)}

def run_editing_design_runtime(fixture: EditingDesignFixture | None = None, *, run_id: str = "editing-design-runtime") -> EditingDesignRuntimeReport:
    fixture = fixture or default_editing_design_frontier_fixture()
    stages: list[EditingDesignRuntimeStage] = []
    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter(); result = fn(); elapsed = round((perf_counter() - started) * 1000, 3); output_address = getattr(result, "content_address", None) or content_hash(result); body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": elapsed, "output_address": output_address, "detail": detail}; stages.append(EditingDesignRuntimeStage(**body, content_address=content_hash(body))); return result
    audit = stage("data-audit", lambda: audit_editing_design_frontier_data(fixture), "audit public source and scenario receipts")
    adapters = stage("adapters", build_editing_design_adapters, "materialize four operation adapters")
    schema = stage("schema", default_editing_design_frontier_schema, "materialize closed input and output fields")
    evaluation = stage("fixture-evaluation", lambda: evaluate_editing_design_fixture(fixture), "execute four positive and twelve control rows")
    metrics = stage("metrics", lambda: measure_editing_design(evaluation), "measure states operations and issues")
    quality = stage("quality-gate", lambda: build_editing_design_quality_gate(audit=audit, evaluation=evaluation, adapters=adapters, schema=schema), "run blocking quality gate")
    integrity = stage("core-integrity", lambda: build_editing_design_integrity(fixture=fixture, evaluation=evaluation), "check content address closure")
    depth = stage("core-depth", lambda: build_editing_design_depth(fixture=fixture, evaluation=evaluation), "assert four operations and eighty checks")
    access = stage("core-access", lambda: build_editing_design_access(fixture=fixture), "describe public aggregate access")
    provenance = stage("assurance-provenance", lambda: build_editing_design_provenance(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run provenance assurance")
    lineage = stage("assurance-lineage", lambda: build_editing_design_lineage(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run lineage assurance")
    reconciliation = stage("assurance-reconciliation", lambda: build_editing_design_reconciliation(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run reconciliation assurance")
    policy = stage("assurance-policy", lambda: build_editing_design_policy(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run policy assurance")
    quality_gate = stage("assurance-quality_gate", lambda: build_editing_design_quality_gate(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run quality_gate assurance")
    replay = stage("assurance-replay", lambda: build_editing_design_replay(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run replay assurance")
    views = stage("assurance-views", lambda: build_editing_design_views(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run views assurance")
    review_queue = stage("assurance-review_queue", lambda: build_editing_design_review_queue(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run review_queue assurance")
    handoff = stage("assurance-handoff", lambda: build_editing_design_handoff(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run handoff assurance")
    integrity = stage("assurance-integrity", lambda: build_editing_design_integrity(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run integrity assurance")
    depth = stage("assurance-depth", lambda: build_editing_design_depth(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run depth assurance")
    controls = stage("assurance-controls", lambda: build_editing_design_controls(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run controls assurance")
    validation_matrix = stage("assurance-validation_matrix", lambda: build_editing_design_validation_matrix(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run validation_matrix assurance")
    evidence_matrix = stage("assurance-evidence_matrix", lambda: build_editing_design_evidence_matrix(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run evidence_matrix assurance")
    access = stage("assurance-access", lambda: build_editing_design_access(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run access assurance")
    failure_injection = stage("assurance-failure_injection", lambda: build_editing_design_failure_injection(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run failure_injection assurance")
    diagnostics = stage("assurance-diagnostics", lambda: build_editing_design_diagnostics(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run diagnostics assurance")
    artifacts = stage("assurance-artifacts", lambda: build_editing_design_artifacts(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run artifacts assurance")
    release = stage("assurance-release", lambda: build_editing_design_release(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run release assurance")
    release_acceptance = stage("assurance-release_acceptance", lambda: build_editing_design_release_acceptance(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run release_acceptance assurance")
    run_manifest = stage("assurance-run_manifest", lambda: build_editing_design_run_manifest(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run run_manifest assurance")
    source_registry = stage("assurance-source_registry", lambda: build_editing_design_source_registry(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run source_registry assurance")
    freshness = stage("assurance-freshness", lambda: build_editing_design_freshness(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run freshness assurance")
    compatibility = stage("assurance-compatibility", lambda: build_editing_design_compatibility(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run compatibility assurance")
    invariants = stage("assurance-invariants", lambda: build_editing_design_invariants(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run invariants assurance")
    execution_plan = stage("assurance-execution_plan", lambda: build_editing_design_execution_plan(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run execution_plan assurance")
    observability = stage("assurance-observability", lambda: build_editing_design_observability(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run observability assurance")
    audit_log = stage("assurance-audit_log", lambda: build_editing_design_audit_log(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run audit_log assurance")
    transcript = stage("assurance-transcript", lambda: build_editing_design_transcript(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run transcript assurance")
    report = stage("assurance-report", lambda: build_editing_design_report(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run report assurance")
    exports = stage("assurance-exports", lambda: build_editing_design_exports(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run exports assurance")
    data_dictionary = stage("assurance-data_dictionary", lambda: build_editing_design_data_dictionary(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run data_dictionary assurance")
    claim_boundary = stage("assurance-claim_boundary", lambda: build_editing_design_claim_boundary(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run claim_boundary assurance")
    recovery = stage("assurance-recovery", lambda: build_editing_design_recovery(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run recovery assurance")
    performance = stage("assurance-performance", lambda: build_editing_design_performance(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run performance assurance")
    operational = stage("assurance-operational", lambda: build_editing_design_operational(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run operational assurance")
    compliance = stage("assurance-compliance", lambda: build_editing_design_compliance(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run compliance assurance")
    query = stage("assurance-query", lambda: build_editing_design_query(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run query assurance")
    partitions = stage("assurance-partitions", lambda: build_editing_design_partitions(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run partitions assurance")
    scenario_matrix = stage("assurance-scenario_matrix", lambda: build_editing_design_scenario_matrix(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run scenario_matrix assurance")
    resources = stage("assurance-resources", lambda: build_editing_design_resources(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run resources assurance")
    bundle = stage("assurance-bundle", lambda: build_editing_design_bundle(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run bundle assurance")
    public_data_boundary = stage("assurance-public_data_boundary", lambda: build_editing_design_public_data_boundary(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run public_data_boundary assurance")
    assurance = stage("assurance-assurance", lambda: build_editing_design_assurance(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run assurance assurance")
    provenance_graph = stage("assurance-provenance_graph", lambda: build_editing_design_provenance_graph(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run provenance_graph assurance")
    decision_ledger = stage("assurance-decision_ledger", lambda: build_editing_design_decision_ledger(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run decision_ledger assurance")
    review_assignment = stage("assurance-review_assignment", lambda: build_editing_design_review_assignment(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run review_assignment assurance")
    schema_diagnostics = stage("assurance-schema_diagnostics", lambda: build_editing_design_schema_diagnostics(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run schema_diagnostics assurance")
    context_boundary = stage("assurance-context_boundary", lambda: build_editing_design_context_boundary(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run context_boundary assurance")
    source_receipt_index = stage("assurance-source_receipt_index", lambda: build_editing_design_source_receipt_index(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run source_receipt_index assurance")
    review_metrics = stage("assurance-review_metrics", lambda: build_editing_design_review_metrics(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run review_metrics assurance")
    review_sla = stage("assurance-review_sla", lambda: build_editing_design_review_sla(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run review_sla assurance")
    review_protocol = stage("assurance-review_protocol", lambda: build_editing_design_review_protocol(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run review_protocol assurance")
    provenance_check = stage("assurance-provenance_check", lambda: build_editing_design_provenance_check(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run provenance_check assurance")
    reproducibility = stage("assurance-reproducibility", lambda: build_editing_design_reproducibility(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run reproducibility assurance")
    attestation = stage("assurance-attestation", lambda: build_editing_design_attestation(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run attestation assurance")
    publication_policy = stage("assurance-publication_policy", lambda: build_editing_design_publication_policy(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run publication_policy assurance")
    operator_console = stage("assurance-operator_console", lambda: build_editing_design_operator_console(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run operator_console assurance")
    contract_migrations = stage("assurance-contract_migrations", lambda: build_editing_design_contract_migrations(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run contract_migrations assurance")
    package_manifest = stage("assurance-package_manifest", lambda: build_editing_design_package_manifest(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run package_manifest assurance")
    source_citations = stage("assurance-source_citations", lambda: build_editing_design_source_citations(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run source_citations assurance")
    outcome_summary = stage("assurance-outcome_summary", lambda: build_editing_design_outcome_summary(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run outcome_summary assurance")
    artifact_manifest = stage("assurance-artifact_manifest", lambda: build_editing_design_artifact_manifest(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run artifact_manifest assurance")
    release_transcript = stage("assurance-release_transcript", lambda: build_editing_design_release_transcript(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run release_transcript assurance")
    scenario_replay = stage("assurance-scenario_replay", lambda: build_editing_design_scenario_replay(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run scenario_replay assurance")
    safety_projection = stage("assurance-safety_projection", lambda: build_editing_design_safety_projection(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run safety_projection assurance")
    state_transition = stage("assurance-state_transition", lambda: build_editing_design_state_transition(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run state_transition assurance")
    boundary_report = stage("assurance-boundary_report", lambda: build_editing_design_boundary_report(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run boundary_report assurance")
    runbook = stage("assurance-runbook", lambda: build_editing_design_runbook(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run runbook assurance")
    summary = stage("assurance-summary", lambda: build_editing_design_summary(fixture=fixture, evaluation=evaluation, quality=quality, integrity=integrity, depth=depth, access=access, adapters=adapters, schema=schema, audit=audit, stages=stages, steps=tuple(item.stage_id for item in stages), run_id=run_id), "run summary assurance")
    planes = {"provenance": provenance, "lineage": lineage, "reconciliation": reconciliation, "policy": policy, "quality_gate": quality_gate, "replay": replay, "views": views, "review_queue": review_queue, "handoff": handoff, "integrity": integrity, "depth": depth, "controls": controls, "validation_matrix": validation_matrix, "evidence_matrix": evidence_matrix, "access": access, "failure_injection": failure_injection, "diagnostics": diagnostics, "artifacts": artifacts, "release": release, "release_acceptance": release_acceptance, "run_manifest": run_manifest, "source_registry": source_registry, "freshness": freshness, "compatibility": compatibility, "invariants": invariants, "execution_plan": execution_plan, "observability": observability, "audit_log": audit_log, "transcript": transcript, "report": report, "exports": exports, "data_dictionary": data_dictionary, "claim_boundary": claim_boundary, "recovery": recovery, "performance": performance, "operational": operational, "compliance": compliance, "query": query, "partitions": partitions, "scenario_matrix": scenario_matrix, "resources": resources, "bundle": bundle, "public_data_boundary": public_data_boundary, "assurance": assurance, "provenance_graph": provenance_graph, "decision_ledger": decision_ledger, "review_assignment": review_assignment, "schema_diagnostics": schema_diagnostics, "context_boundary": context_boundary, "source_receipt_index": source_receipt_index, "review_metrics": review_metrics, "review_sla": review_sla, "review_protocol": review_protocol, "provenance_check": provenance_check, "reproducibility": reproducibility, "attestation": attestation, "publication_policy": publication_policy, "operator_console": operator_console, "contract_migrations": contract_migrations, "package_manifest": package_manifest, "source_citations": source_citations, "outcome_summary": outcome_summary, "artifact_manifest": artifact_manifest, "release_transcript": release_transcript, "scenario_replay": scenario_replay, "safety_projection": safety_projection, "state_transition": state_transition, "boundary_report": boundary_report, "runbook": runbook, "summary": summary}
    accepted = bool(audit.accepted and evaluation.accepted and quality.accepted and integrity.accepted and depth.accepted and access.accepted and all(getattr(item, "accepted", False) for item in planes.values()))
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "audit": audit, "adapters": adapters, "schema": schema, "evaluation": evaluation, "metrics": metrics, "planes": planes, "accepted": accepted}
    return EditingDesignRuntimeReport(**body, content_address=content_hash(body))

__all__ = ["EditingDesignRuntimeReport", "EditingDesignRuntimeStage", "run_editing_design_runtime"]
