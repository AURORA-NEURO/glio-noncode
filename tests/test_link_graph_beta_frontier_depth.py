"""Independent depth checks for the Domain 10 C05-C08 beta plane."""

from __future__ import annotations

import json

import pytest

from glio_noncode.link_graph_beta_frontier_artifacts import build_link_graph_beta_frontier_artifacts
from glio_noncode.link_graph_beta_frontier_assurance_summary import build_link_graph_beta_frontier_assurance_summary
from glio_noncode.link_graph_beta_frontier_audit_trail import (
    audit_trail_summary,
    build_link_graph_beta_frontier_audit_trail,
)
from glio_noncode.link_graph_beta_frontier_benchmark import build_link_graph_beta_frontier_benchmark
from glio_noncode.link_graph_beta_frontier_bundle import build_link_graph_beta_frontier_bundle
from glio_noncode.link_graph_beta_frontier_catalog import (
    build_link_graph_beta_frontier_module_catalog,
    module_catalog_summary,
)
from glio_noncode.link_graph_beta_frontier_claim_boundary import build_link_graph_beta_frontier_claim_boundary
from glio_noncode.link_graph_beta_frontier_comparison import build_link_graph_beta_frontier_comparison
from glio_noncode.link_graph_beta_frontier_conformance import evaluate_link_graph_beta_frontier_conformance
from glio_noncode.link_graph_beta_frontier_control_catalog import build_link_graph_beta_frontier_control_catalog
from glio_noncode.link_graph_beta_frontier_coverage_matrix import (
    build_link_graph_beta_frontier_coverage_matrix,
    coverage_matrix_summary,
)
from glio_noncode.link_graph_beta_frontier_decision_table import (
    build_link_graph_beta_frontier_decision_table,
    decision_table_summary,
)
from glio_noncode.link_graph_beta_frontier_decision_trace import (
    build_link_graph_beta_frontier_decision_traces,
    decision_trace_summary,
)
from glio_noncode.link_graph_beta_frontier_export_manifest import build_link_graph_beta_frontier_export_manifest
from glio_noncode.link_graph_beta_frontier_failure_catalog import build_link_graph_beta_frontier_failure_catalog
from glio_noncode.link_graph_beta_frontier_field_projection import (
    build_link_graph_beta_frontier_projection_schema,
    project_link_graph_beta_frontier_evaluation,
    project_link_graph_beta_frontier_fixture,
)
from glio_noncode.link_graph_beta_frontier_field_validation import validate_link_graph_beta_frontier_fields
from glio_noncode.link_graph_beta_frontier_fixture_eval import evaluate_link_graph_beta_frontier_fixture
from glio_noncode.link_graph_beta_frontier_history import build_link_graph_beta_frontier_history
from glio_noncode.link_graph_beta_frontier_integrity import evaluate_link_graph_beta_frontier_integrity
from glio_noncode.link_graph_beta_frontier_invariant_catalog import evaluate_link_graph_beta_frontier_invariant_catalog
from glio_noncode.link_graph_beta_frontier_lineage import (
    build_link_graph_beta_frontier_lineage,
    verify_link_graph_beta_frontier_lineage,
)
from glio_noncode.link_graph_beta_frontier_manifest_serialization import (
    deserialize_link_graph_beta_frontier_manifest,
    manifest_serialization_address,
    serialize_link_graph_beta_frontier_manifest,
)
from glio_noncode.link_graph_beta_frontier_metrics import build_link_graph_beta_frontier_metrics
from glio_noncode.link_graph_beta_frontier_normalization import (
    normalize_link_graph_beta_frontier_fixture,
    normalization_summary,
)
from glio_noncode.link_graph_beta_frontier_performance import (
    evaluate_link_graph_beta_frontier_performance,
    performance_summary,
)
from glio_noncode.link_graph_beta_frontier_pipeline import run_link_graph_beta_frontier_pipeline
from glio_noncode.link_graph_beta_frontier_policy import evaluate_link_graph_beta_frontier_policy
from glio_noncode.link_graph_beta_frontier_projection_diff import compare_link_graph_beta_frontier_fixture_to_self
from glio_noncode.link_graph_beta_frontier_provenance import build_link_graph_beta_frontier_provenance
from glio_noncode.link_graph_beta_frontier_public_data import (
    LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY,
    LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY,
    LinkGraphBetaFrontierOperation,
    audit_link_graph_beta_frontier_data,
    default_link_graph_beta_frontier_fixture,
)
from glio_noncode.link_graph_beta_frontier_quality_dashboard import (
    build_link_graph_beta_frontier_quality_dashboard,
    quality_dashboard_summary,
)
from glio_noncode.link_graph_beta_frontier_query_plan import build_link_graph_beta_frontier_query_plans
from glio_noncode.link_graph_beta_frontier_receipt_ledger import (
    build_link_graph_beta_frontier_receipt_ledger,
    receipt_coverage_by_operation,
)
from glio_noncode.link_graph_beta_frontier_release_readiness import (
    build_link_graph_beta_frontier_release_readiness,
    release_readiness_summary,
)
from glio_noncode.link_graph_beta_frontier_replay import (
    build_link_graph_beta_frontier_expectations,
    replay_link_graph_beta_frontier,
)
from glio_noncode.link_graph_beta_frontier_report_render import (
    render_link_graph_beta_frontier_summary_markdown,
    render_link_graph_beta_frontier_table,
)
from glio_noncode.link_graph_beta_frontier_risk_register import (
    build_link_graph_beta_frontier_risk_register,
    risk_register_summary,
)
from glio_noncode.link_graph_beta_frontier_scenario_catalog import (
    build_link_graph_beta_frontier_scenario_catalog,
    scenario_catalog_summary,
)
from glio_noncode.link_graph_beta_frontier_scenario_matrix import build_link_graph_beta_frontier_scenario_matrix
from glio_noncode.link_graph_beta_frontier_schema import validate_link_graph_beta_frontier_schema
from glio_noncode.link_graph_beta_frontier_source_checks import run_link_graph_beta_frontier_source_checks
from glio_noncode.link_graph_beta_frontier_source_registry import build_link_graph_beta_frontier_source_registry
from glio_noncode.link_graph_beta_frontier_support import issue_counts, operation_counts, state_counts
from glio_noncode.link_graph_beta_frontier_traceability import (
    build_link_graph_beta_frontier_traceability,
    traceability_summary,
)
from glio_noncode.link_graph_beta_frontier_validation_matrix import build_link_graph_beta_frontier_validation_matrix
from glio_noncode.link_graph_beta_frontier_validation_orchestration import (
    run_link_graph_beta_frontier_validation_orchestration,
    validation_orchestration_summary,
)
from glio_noncode.link_graph_beta_frontier_workflow import run_link_graph_beta_frontier_workflow, workflow_summary


@pytest.fixture(scope="module")
def fixture():
    return default_link_graph_beta_frontier_fixture()


@pytest.fixture(scope="module")
def evaluation(fixture):
    return evaluate_link_graph_beta_frontier_fixture(fixture)


@pytest.fixture(scope="module")
def pipeline(fixture):
    return run_link_graph_beta_frontier_pipeline(fixture, run_id="beta-depth")


def test_fixture_has_four_operations_and_four_rows_each(fixture):
    assert tuple(item.value for item in LinkGraphBetaFrontierOperation) == (
        "activity_by_contact",
        "coaccessibility",
        "molecular_qtl",
        "allele_specific",
    )
    assert operation_counts(fixture) == {
        "activity_by_contact": 4,
        "coaccessibility": 4,
        "molecular_qtl": 4,
        "allele_specific": 4,
    }


def test_fixture_audit_enforces_public_aggregate_boundary(fixture):
    audit = audit_link_graph_beta_frontier_data(fixture)
    assert audit.accepted
    assert fixture.boundary == "public_aggregate_non_patient"
    assert audit.record_count == 16
    assert audit.source_count == 4
    assert audit.positive_count == 4
    assert audit.control_count == 12
    assert sum(item.context_key == LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY for item in fixture.records) == 4
    assert sum(item.expected_state == "abstained" for item in fixture.records) == 4


def test_context_partition_is_explicit(fixture):
    target = tuple(item for item in fixture.records if item.context_key == LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY)
    foreign = tuple(item for item in fixture.records if item.context_key == LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY)
    assert len(target) == 12
    assert len(foreign) == 4
    assert all(item.context_key != LINK_GRAPH_BETA_FRONTIER_FOREIGN_CONTEXT_KEY for item in target)
    assert all(item.role.value == "control" for item in foreign)
    assert all("context_mismatch" in item.expected_issue_codes for item in foreign)


def test_evaluation_preserves_expected_states_and_issues(evaluation):
    assert evaluation.accepted
    assert evaluation.state_match_count == 16
    assert evaluation.issue_match_count == 16
    assert not evaluation.failed_record_ids
    assert state_counts(evaluation) == {"partial": 7, "abstained": 4, "out_of_domain": 4, "contradictory": 1}
    assert issue_counts(evaluation) == {
        "single_method": 3,
        "replicate_pair": 1,
        "missing_evidence": 4,
        "context_mismatch": 4,
        "alternative_gene": 1,
        "weak_q_value": 1,
        "single_direction": 1,
        "direction_conflict": 1,
    }


@pytest.mark.parametrize(
    ("operation", "positive_id", "control_ids"),
    (
        ("activity_by_contact", "D10-C05-P", ("D10-C05-C1", "D10-C05-C2", "D10-C05-C3")),
        ("coaccessibility", "D10-C06-P", ("D10-C06-C1", "D10-C06-C2", "D10-C06-C3")),
        ("molecular_qtl", "D10-C07-P", ("D10-C07-C1", "D10-C07-C2", "D10-C07-C3")),
        ("allele_specific", "D10-C08-P", ("D10-C08-C1", "D10-C08-C2", "D10-C08-C3")),
    ),
)
def test_operation_rows_keep_positive_and_control_roles(fixture, evaluation, operation, positive_id, control_ids):
    rows = evaluation.by_operation(operation)
    records = tuple(item for item in fixture.records if item.operation.value == operation)
    assert len(rows) == 4
    assert len(records) == 4
    assert next(item for item in records if item.record_id == positive_id).role.value == "positive"
    assert {item.record_id for item in records if item.role.value == "control"} == set(control_ids)
    assert {item.record_id for item in rows} == {item.record_id for item in records}


def test_contract_and_adapter_surfaces_are_closed(fixture):
    contracts = run_link_graph_beta_frontier_pipeline(fixture).contracts
    adapters = run_link_graph_beta_frontier_pipeline(fixture).sources
    assert contracts.accepted
    assert len(contracts.contracts) == 4
    assert all(item.required_fields and item.output_fields and item.limitation for item in contracts.contracts)
    assert adapters.accepted
    assert len(adapters.sources) == 4
    assert all(item.source_id for item in adapters.sources)


def test_source_registry_and_source_checks_agree(fixture):
    registry = build_link_graph_beta_frontier_source_registry(fixture)
    checks = run_link_graph_beta_frontier_source_checks(fixture)
    assert registry.accepted
    assert checks.accepted
    assert len(registry.sources) == len(checks.checks) == 4
    assert all(item["passed"] for item in checks.checks)
    assert {item.source_id for item in registry.sources} == {item["check_id"] for item in checks.checks}


def test_projection_schema_is_stable_and_complete(fixture, evaluation):
    schema = build_link_graph_beta_frontier_projection_schema()
    fixture_projection = project_link_graph_beta_frontier_fixture(fixture)
    evaluation_rows = project_link_graph_beta_frontier_evaluation(evaluation)
    assert fixture_projection.accepted
    assert fixture_projection.schema.names() == schema.names()
    assert len(fixture_projection.rows) == len(evaluation_rows) == 16
    assert schema.names() == (
        "record_id",
        "operation",
        "role",
        "context_key",
        "expected_state",
        "expected_issue_codes",
        "source_ids",
    )
    assert all(set(row) == set(schema.names()) for row in fixture_projection.rows)


def test_normalization_is_idempotent(fixture):
    first = normalize_link_graph_beta_frontier_fixture(fixture)
    second = normalize_link_graph_beta_frontier_fixture(fixture)
    assert first.accepted
    assert normalization_summary(first)["unique_record_ids"] is True
    assert first.to_dict(False) == second.to_dict(False)
    assert tuple(item.record_id for item in first.records) == tuple(item.record_id for item in fixture.records)


def test_schema_and_field_validation_cover_required_receipts(fixture, evaluation):
    schema = validate_link_graph_beta_frontier_schema(fixture, evaluation)
    fields = validate_link_graph_beta_frontier_fields(fixture)
    assert schema.accepted
    assert fields.accepted
    assert len(schema.fields) == 9
    assert len(schema.checks) == 5
    assert len(fields.checks) == 5
    assert schema.field("record_id").required
    assert not fields.failed_fields


def test_metrics_reconcile_per_operation_counts(fixture, evaluation):
    metrics = build_link_graph_beta_frontier_metrics(evaluation, fixture)
    assert metrics.accepted
    assert metrics.state_accuracy == 1.0
    assert len(metrics.operations) == 4
    assert all(item.record_count == 4 for item in metrics.operations)
    assert all(item.state_matches == item.issue_matches == 4 for item in metrics.operations)


def test_lineage_and_provenance_have_no_orphans(fixture, evaluation):
    lineage = build_link_graph_beta_frontier_lineage(fixture, evaluation)
    provenance = build_link_graph_beta_frontier_provenance(fixture, evaluation)
    assert lineage.accepted
    assert verify_link_graph_beta_frontier_lineage(lineage, fixture)
    assert len(lineage.edges) == 32
    assert len(lineage.record_edges) == 16
    assert provenance.accepted
    assert len(provenance.nodes) == 36
    assert len(provenance.edges) == 32
    assert all(node.node_id for node in provenance.nodes)


def test_policy_and_failure_catalog_explain_boundary_cases(evaluation):
    policy = evaluate_link_graph_beta_frontier_policy(evaluation)
    failures = build_link_graph_beta_frontier_failure_catalog(evaluation)
    assert policy.accepted
    assert len(policy.decisions) == 16
    assert failures.accepted
    assert len(failures.definitions) == 5
    assert set(failures.observed_failure_ids) == {"context-mismatch", "direction-conflict", "missing-evidence"}
    assert next(item for item in policy.decisions if item.record_id == "D10-C05-C2").disposition == "abstain"
    assert next(item for item in policy.decisions if item.record_id == "D10-C08-C1").disposition == "abstain"


def test_comparison_and_projection_diff_are_zero_mismatch(evaluation, fixture):
    comparison = build_link_graph_beta_frontier_comparison(evaluation, fixture)
    diff = compare_link_graph_beta_frontier_fixture_to_self(fixture)
    assert comparison.accepted
    assert len(comparison.cells) == 48
    assert len(comparison.by_dimension("state")) == 16
    assert len(comparison.by_dimension("issues")) == 16
    assert len(comparison.by_dimension("operation")) == 16
    assert not comparison.mismatches
    assert diff.equal
    assert not diff.changed_record_ids
    assert len(diff.cells) == 16 * 7


def test_decision_traces_cover_every_row_and_four_steps(evaluation):
    traces = build_link_graph_beta_frontier_decision_traces(evaluation)
    summary = decision_trace_summary(traces)
    assert len(traces) == 16
    assert summary == {"trace_count": 16, "step_count": 64, "accepted_count": 16, "operation_count": 4}
    assert all(len(item.steps) == 4 for item in traces)
    assert all(item.step("context").result == "accepted" for item in traces)
    assert all(item.step("issues").result for item in traces)


def test_conformance_and_invariant_catalog_are_independent(fixture, evaluation):
    conformance = evaluate_link_graph_beta_frontier_conformance(fixture, evaluation)
    catalog = evaluate_link_graph_beta_frontier_invariant_catalog(fixture, evaluation)
    assert conformance.accepted
    assert catalog.accepted
    assert len(conformance.results) == 6
    assert len(catalog.results) == 6
    assert not conformance.failed_rules
    assert not catalog.blocking_failures


def test_coverage_validation_and_decision_tables_have_full_rows(fixture, evaluation):
    coverage = build_link_graph_beta_frontier_coverage_matrix(fixture, evaluation)
    validation = build_link_graph_beta_frontier_validation_matrix(evaluation)
    decisions = build_link_graph_beta_frontier_decision_table(fixture, evaluation)
    assert coverage.accepted
    assert validation.accepted
    assert decisions.accepted
    assert coverage_matrix_summary(coverage)["cell_count"] == 16
    assert len(validation.cells) == 16
    assert decision_table_summary(decisions)["rule_count"] == 16
    assert not coverage.failed_cells
    assert not validation.failed_cells
    assert not decisions.failed_rules


def test_benchmark_performance_and_quality_dashboard_are_green(fixture, evaluation):
    benchmark = build_link_graph_beta_frontier_benchmark(evaluation, fixture)
    performance = evaluate_link_graph_beta_frontier_performance(fixture, evaluation)
    dashboard = build_link_graph_beta_frontier_quality_dashboard(fixture, evaluation, benchmark=benchmark, performance=performance)
    assert benchmark.accepted
    assert performance.accepted
    assert dashboard.accepted
    assert len(benchmark.cases) == len(benchmark.results) == 4
    assert all(item.accepted for item in benchmark.results)
    assert performance_summary(performance)["budget_count"] == 4
    assert quality_dashboard_summary(dashboard)["passed_count"] == 5
    assert not dashboard.failed_indicators


def test_receipt_ledger_covers_each_operation(fixture):
    ledger = build_link_graph_beta_frontier_receipt_ledger(fixture)
    coverage = receipt_coverage_by_operation(ledger, fixture)
    assert ledger.accepted
    assert ledger.covered_record_count == 16
    assert not ledger.uncovered_record_ids
    assert coverage == {"activity_by_contact": 4, "allele_specific": 4, "coaccessibility": 4, "molecular_qtl": 4}
    assert all(item.complete for item in ledger.entries)


def test_release_manifest_has_only_declared_artifacts(fixture, evaluation):
    manifest = build_link_graph_beta_frontier_export_manifest(fixture, evaluation)
    assert manifest.accepted
    assert len(manifest.artifacts) == 2
    assert {item.artifact_id for item in manifest.artifacts} == {"fixture-records", "replay-results"}
    assert all(item.media_type == "application/json" for item in manifest.artifacts)
    assert all(item.content_address.startswith("sha256:") for item in manifest.artifacts)


def test_manifest_serialization_is_json_safe(fixture, evaluation):
    manifest = build_link_graph_beta_frontier_export_manifest(fixture, evaluation)
    encoded = serialize_link_graph_beta_frontier_manifest(manifest)
    decoded = deserialize_link_graph_beta_frontier_manifest(encoded)
    assert json.loads(encoded) == decoded
    assert decoded["fixture_id"] == fixture.fixture_id
    assert manifest_serialization_address(manifest).startswith("sha256:")


def test_review_and_claim_boundaries_are_explicit(fixture, evaluation):
    queue = run_link_graph_beta_frontier_pipeline(fixture).review_queue
    boundary = build_link_graph_beta_frontier_claim_boundary()
    assert queue.accepted
    assert len(queue.entries) == 16
    assert boundary.accepted
    assert boundary.boundary == "public_aggregate_non_patient"
    assert "patient-level inference" in boundary.prohibited_claims
    assert "method-specific support" in boundary.allowed_claims


def test_history_and_control_catalog_are_auditable(fixture, evaluation):
    history = build_link_graph_beta_frontier_history()
    controls = build_link_graph_beta_frontier_control_catalog(evaluation)
    assert len(history.entries) == 2
    assert all(item.version and item.change and item.accepted for item in history.entries)
    assert controls.accepted
    assert len(controls.controls) == 6
    assert len(controls.for_issue("missing_evidence")) == 1
    assert all(item.rationale for item in controls.controls)


def test_audit_trail_is_chain_valid(fixture, evaluation):
    trail = build_link_graph_beta_frontier_audit_trail(fixture, evaluation)
    summary = audit_trail_summary(trail)
    assert trail.accepted
    assert trail.chain_valid
    assert summary["event_count"] == 16
    assert all(item.previous_address for item in trail.events[1:])
    assert trail.events[0].previous_address == ""


def test_scenario_catalog_and_matrix_retain_control_states(fixture, evaluation):
    catalog = build_link_graph_beta_frontier_scenario_catalog(fixture, evaluation)
    matrix = build_link_graph_beta_frontier_scenario_matrix(evaluation)
    assert catalog.accepted
    assert matrix.accepted
    assert scenario_catalog_summary(catalog)["definition_count"] == 16
    assert len(catalog.definitions) == len(catalog.outcomes) == 16
    assert len(matrix.cells) == 16
    assert not catalog.failed_scenarios
    assert not matrix.failed_cells
    assert catalog.outcome("scenario-d10-c08-c1").observed_states == ("contradictory",)


def test_traceability_and_orchestration_roll_up_the_same_fixture(fixture):
    traceability = build_link_graph_beta_frontier_traceability(fixture)
    orchestration = run_link_graph_beta_frontier_validation_orchestration(fixture)
    assert traceability.accepted
    assert orchestration.accepted
    assert traceability_summary(traceability)["item_count"] == 4
    assert validation_orchestration_summary(orchestration)["check_count"] == 7
    assert not traceability.failed_items
    assert not orchestration.failed_checks


def test_workflow_and_release_readiness_agree(pipeline):
    workflow = run_link_graph_beta_frontier_workflow(pipeline.fixture)
    readiness = build_link_graph_beta_frontier_release_readiness(
        pipeline.fixture,
        pipeline.evaluation,
        benchmark=build_link_graph_beta_frontier_benchmark(pipeline.evaluation, pipeline.fixture),
        conformance=evaluate_link_graph_beta_frontier_conformance(pipeline.fixture, pipeline.evaluation),
        invariants=evaluate_link_graph_beta_frontier_invariant_catalog(pipeline.fixture, pipeline.evaluation),
        performance=evaluate_link_graph_beta_frontier_performance(pipeline.fixture, pipeline.evaluation),
        manifest=build_link_graph_beta_frontier_export_manifest(pipeline.fixture, pipeline.evaluation),
    )
    assert workflow.accepted
    assert readiness.publishable
    assert workflow_summary(workflow)["stage_count"] == 6
    assert release_readiness_summary(readiness)["check_count"] == 7
    assert workflow.readiness.publishable
    assert not readiness.failed_checks


def test_module_catalog_names_each_operational_layer():
    catalog = build_link_graph_beta_frontier_module_catalog()
    summary = module_catalog_summary(catalog)
    assert catalog.accepted
    assert summary["module_count"] == 7
    assert summary["layer_count"] == 7
    assert set(summary["layers"]) == {"compute", "data", "operations", "quality", "release", "replay", "review"}
    assert all(item.module_id and item.test_file for item in catalog.entries)


def test_pipeline_exposes_assurance_summary_and_artifact_bundle(pipeline):
    summary = build_link_graph_beta_frontier_assurance_summary(pipeline)
    bundle = build_link_graph_beta_frontier_bundle(
        pipeline.fixture,
        pipeline.release,
        pipeline.metrics,
        pipeline.lineage,
    )
    artifacts = build_link_graph_beta_frontier_artifacts(bundle, pipeline.evaluation)
    assert summary.accepted
    assert bundle.accepted
    assert artifacts.accepted
    assert summary.stage_count == 12
    assert summary.passed_stage_count == 12
    assert summary.record_count == 16
    assert summary.source_count == 4
    assert summary.artifact_count == 4
    assert len(artifacts.artifacts) == 4


def test_pipeline_replay_is_repeatable(pipeline):
    expectations = build_link_graph_beta_frontier_expectations(pipeline.evaluation)
    first = replay_link_graph_beta_frontier(pipeline.evaluation, expectations)
    second = replay_link_graph_beta_frontier(pipeline.evaluation, expectations)
    assert first.accepted and second.accepted
    assert first.to_dict(False) == second.to_dict(False)
    assert len(first.expectations) == first.matched_count == 16
    assert not first.failed_record_ids


def test_pipeline_has_all_named_stages(pipeline):
    assert pipeline.accepted
    assert tuple(item.stage_id for item in pipeline.stages) == (
        "data_audit",
        "contracts",
        "sources",
        "evaluation",
        "schema",
        "metrics",
        "lineage",
        "quality",
        "validation",
        "review",
        "release",
        "artifacts",
    )
    assert all(item.status == "passed" for item in pipeline.stages)
    assert not pipeline.failed_stages


def test_json_renderers_are_deterministic(fixture, evaluation):
    summary = {
        "fixture_id": fixture.fixture_id,
        "record_count": len(fixture.records),
        "accepted": evaluation.accepted,
    }
    rows = tuple(item.to_dict() for item in evaluation.rows)
    first_summary = render_link_graph_beta_frontier_summary_markdown(summary)
    second_summary = render_link_graph_beta_frontier_summary_markdown(summary)
    first_table = render_link_graph_beta_frontier_table(rows)
    second_table = render_link_graph_beta_frontier_table(rows)
    assert first_summary == second_summary
    assert first_table == second_table
    assert "link-graph-beta-frontier-fixture" in first_summary
    assert "record_id" in first_table


def test_query_plans_are_closed_and_addressed():
    plans = build_link_graph_beta_frontier_query_plans()
    assert plans.accepted
    assert len(plans.plans) == 4
    assert {item.query_id for item in plans.plans} == {
        "context-boundary",
        "operation-balance",
        "direction-conflicts",
        "review-controls",
    }
    assert all(item.limitation for item in plans.plans)


def test_depth_report_is_clean(fixture, evaluation):
    from glio_noncode.link_graph_beta_frontier_depth import audit_link_graph_beta_frontier_depth

    report = audit_link_graph_beta_frontier_depth(fixture, evaluation)
    assert report.accepted
    assert len(report.checks) == 5
    assert not report.failed_checks
