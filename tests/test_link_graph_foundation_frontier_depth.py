"""Independent depth checks for the Domain 10 C01-C04 foundation plane."""

from __future__ import annotations

import json

import pytest

from glio_noncode.link_graph_foundation_frontier_acceptance_matrix import (
    acceptance_matrix_summary,
    build_link_graph_foundation_frontier_acceptance_matrix,
)
from glio_noncode.link_graph_foundation_frontier_assertions import (
    assertion_summary,
    evaluate_link_graph_foundation_frontier_assertions,
)
from glio_noncode.link_graph_foundation_frontier_audit_trail import (
    audit_trail_summary,
    build_link_graph_foundation_frontier_audit_trail,
)
from glio_noncode.link_graph_foundation_frontier_benchmark import (
    benchmark_link_graph_foundation_frontier_operation,
    build_link_graph_foundation_frontier_benchmark,
)
from glio_noncode.link_graph_foundation_frontier_catalog import (
    build_link_graph_foundation_frontier_module_catalog,
    module_catalog_summary,
)
from glio_noncode.link_graph_foundation_frontier_comparison import (
    build_link_graph_foundation_frontier_comparison,
    compare_link_graph_foundation_frontier_metrics,
)
from glio_noncode.link_graph_foundation_frontier_conformance import (
    evaluate_link_graph_foundation_frontier_conformance,
)
from glio_noncode.link_graph_foundation_frontier_decision_trace import (
    build_link_graph_foundation_frontier_decision_traces,
    decision_trace_summary,
)
from glio_noncode.link_graph_foundation_frontier_export_manifest import (
    build_link_graph_foundation_frontier_export_manifest,
    export_link_graph_foundation_frontier_manifest,
)
from glio_noncode.link_graph_foundation_frontier_field_projection import (
    build_link_graph_foundation_frontier_projection_schema,
    project_link_graph_foundation_frontier_evaluation,
    project_link_graph_foundation_frontier_fixture,
)
from glio_noncode.link_graph_foundation_frontier_field_validation import (
    validate_link_graph_foundation_frontier_fields,
)
from glio_noncode.link_graph_foundation_frontier_fixture_eval import (
    evaluate_link_graph_foundation_frontier_fixture,
)
from glio_noncode.link_graph_foundation_frontier_invariant_catalog import (
    evaluate_link_graph_foundation_frontier_invariants,
)
from glio_noncode.link_graph_foundation_frontier_normalization import (
    normalize_link_graph_foundation_frontier_fixture,
    normalization_summary,
)
from glio_noncode.link_graph_foundation_frontier_operation_contracts import (
    build_link_graph_foundation_frontier_operation_contracts,
    operation_contract_summary,
)
from glio_noncode.link_graph_foundation_frontier_performance import (
    evaluate_link_graph_foundation_frontier_performance,
    performance_summary,
)
from glio_noncode.link_graph_foundation_frontier_provenance_matrix import (
    build_link_graph_foundation_frontier_provenance_matrix,
    provenance_matrix_summary,
)
from glio_noncode.link_graph_foundation_frontier_projection_diff import (
    compare_link_graph_foundation_frontier_fixture_to_self,
)
from glio_noncode.link_graph_foundation_frontier_public_data import (
    default_link_graph_foundation_frontier_fixture,
)
from glio_noncode.link_graph_foundation_frontier_quality_dashboard import (
    build_link_graph_foundation_frontier_quality_dashboard,
    quality_dashboard_summary,
)
from glio_noncode.link_graph_foundation_frontier_receipt_ledger import (
    build_link_graph_foundation_frontier_receipt_ledger,
    receipt_coverage_by_operation,
)
from glio_noncode.link_graph_foundation_frontier_regression import (
    evaluate_link_graph_foundation_frontier_regressions,
    operation_regression_counts,
)
from glio_noncode.link_graph_foundation_frontier_release_readiness import (
    build_link_graph_foundation_frontier_release_readiness,
    release_readiness_summary,
)
from glio_noncode.link_graph_foundation_frontier_review_packet import (
    build_link_graph_foundation_frontier_review_packet,
    review_packet_summary,
)
from glio_noncode.link_graph_foundation_frontier_risk_register import (
    build_link_graph_foundation_frontier_risk_register,
    risk_register_summary,
)
from glio_noncode.link_graph_foundation_frontier_sampling import (
    build_link_graph_foundation_frontier_sampling,
    sample_link_graph_foundation_frontier_evaluation,
)
from glio_noncode.link_graph_foundation_frontier_workflow import (
    run_link_graph_foundation_frontier_workflow,
    workflow_summary,
)


@pytest.fixture(scope="module")
def fixture():
    return default_link_graph_foundation_frontier_fixture()


@pytest.fixture(scope="module")
def evaluation():
    return evaluate_link_graph_foundation_frontier_fixture()


def test_benchmark_has_one_case_per_operation(fixture, evaluation):
    report = build_link_graph_foundation_frontier_benchmark(evaluation, fixture)
    assert report.accepted
    assert report.operation_count == 4
    assert not report.failed_case_ids
    assert all(item.within_budget for item in report.results)


@pytest.mark.parametrize(
    "operation",
    (
        "coordinate_overlap",
        "nearest_gene",
        "ccre_assignment",
        "enhancer_gene_consensus",
    ),
)
def test_single_operation_benchmark(operation, evaluation):
    result = benchmark_link_graph_foundation_frontier_operation(operation, evaluation)
    assert result.accepted
    assert result.operation == operation
    assert result.observed_states


def test_comparison_cells_cover_state_issue_and_operation(fixture, evaluation):
    report = build_link_graph_foundation_frontier_comparison(evaluation, fixture)
    assert report.accepted
    assert len(report.cells) == 48
    assert not report.mismatches
    assert len(report.by_dimension("state")) == 16
    assert len(report.by_dimension("issues")) == 16
    assert len(report.by_dimension("operation")) == 16


def test_projection_schema_is_stable(fixture, evaluation):
    schema = build_link_graph_foundation_frontier_projection_schema()
    report = project_link_graph_foundation_frontier_fixture(fixture)
    rows = project_link_graph_foundation_frontier_evaluation(evaluation)
    assert report.accepted
    assert report.schema.names() == tuple(item.name for item in schema.fields)
    assert len(report.rows) == len(fixture.records)
    assert len(rows) == len(evaluation.rows)
    assert {"record_id", "operation", "context_key"} <= set(schema.names())


def test_conformance_and_invariants_are_independent(fixture, evaluation):
    conformance = evaluate_link_graph_foundation_frontier_conformance(fixture, evaluation)
    invariants = evaluate_link_graph_foundation_frontier_invariants(fixture, evaluation)
    assert conformance.accepted
    assert invariants.accepted
    assert not conformance.failed_rules
    assert not invariants.blocking_failures
    assert len(conformance.results) == 6
    assert len(invariants.results) == 7


def test_acceptance_matrix_has_each_declared_outcome(evaluation):
    matrix = build_link_graph_foundation_frontier_acceptance_matrix(evaluation)
    summary = acceptance_matrix_summary(matrix)
    assert matrix.accepted
    assert summary["cell_count"] >= 10
    assert summary["passed_cells"] == summary["cell_count"]
    assert not matrix.failed_cells


def test_receipts_cover_every_record(fixture):
    ledger = build_link_graph_foundation_frontier_receipt_ledger(fixture)
    coverage = receipt_coverage_by_operation(ledger, fixture)
    assert ledger.accepted
    assert ledger.covered_record_count == 16
    assert not ledger.uncovered_record_ids
    assert set(coverage) == {
        "coordinate_overlap",
        "nearest_gene",
        "ccre_assignment",
        "enhancer_gene_consensus",
    }
    assert all(value == 4 for value in coverage.values())


def test_operation_contracts_are_closed():
    catalog = build_link_graph_foundation_frontier_operation_contracts()
    summary = operation_contract_summary(catalog)
    assert catalog.accepted
    assert len(catalog.contracts) == 4
    assert summary["required_input_count"] >= 12
    assert all(catalog.for_operation(item.operation).limitations for item in catalog.contracts)


def test_quality_dashboard_rolls_up_all_indicators(fixture, evaluation):
    dashboard = build_link_graph_foundation_frontier_quality_dashboard(fixture, evaluation)
    summary = quality_dashboard_summary(dashboard)
    assert dashboard.accepted
    assert summary["indicator_count"] == 5
    assert summary["passed_count"] == 5
    assert not dashboard.failed_indicators


def test_field_validation_and_normalization(fixture):
    fields = validate_link_graph_foundation_frontier_fields(fixture)
    normalized = normalize_link_graph_foundation_frontier_fixture(fixture)
    summary = normalization_summary(normalized)
    assert fields.accepted
    assert normalized.accepted
    assert normalized.unique_record_ids
    assert normalized.stable_order
    assert summary["record_count"] == 16
    assert not fields.failed_fields


def test_performance_report_is_bounded(fixture, evaluation):
    report = evaluate_link_graph_foundation_frontier_performance(fixture, evaluation)
    summary = performance_summary(report)
    assert report.accepted
    assert summary["observation_count"] == 4
    assert summary["work_units"] <= 256
    assert not report.failed_budgets


def test_decision_traces_are_ordered(fixture, evaluation):
    traces = build_link_graph_foundation_frontier_decision_traces(evaluation, fixture)
    summary = decision_trace_summary(traces)
    assert len(traces) == 16
    assert summary["step_count"] == 64
    assert summary["accepted_count"] == 16
    assert all(tuple(step.sequence for step in trace.steps) == (1, 2, 3, 4) for trace in traces)


def test_provenance_matrix_is_complete(fixture, evaluation):
    matrix = build_link_graph_foundation_frontier_provenance_matrix(fixture, evaluation)
    summary = provenance_matrix_summary(matrix)
    assert matrix.complete
    assert summary["cell_count"] == 16
    assert summary["source_count"] == 5
    assert not matrix.incomplete_record_ids


def test_regression_sentinels_are_green(fixture, evaluation):
    report = evaluate_link_graph_foundation_frontier_regressions(evaluation, fixture)
    counts = operation_regression_counts(report)
    assert report.accepted
    assert not report.failures
    assert sum(counts.values()) == 5
    assert counts["coordinate_overlap"] == 2
    assert counts["enhancer_gene_consensus"] == 1


def test_release_readiness_is_publishable(fixture, evaluation):
    report = build_link_graph_foundation_frontier_release_readiness(fixture, evaluation)
    summary = release_readiness_summary(report)
    assert report.publishable
    assert summary["check_count"] == 7
    assert summary["passed_count"] == 7
    assert not report.failed_checks


def test_sampling_covers_fixture_without_overlap(fixture, evaluation):
    report = build_link_graph_foundation_frontier_sampling(fixture, window_size=4)
    rows = sample_link_graph_foundation_frontier_evaluation(evaluation, offset=4, limit=4)
    assert report.accepted
    assert len(report.windows) == 4
    assert report.coverage_count == 16
    assert len(set(report.covered_record_ids)) == 16
    assert len(rows) == 4


def test_risk_register_has_nonblocking_controls():
    register = build_link_graph_foundation_frontier_risk_register()
    summary = risk_register_summary(register)
    assert register.accepted
    assert summary["risk_count"] == 5
    assert summary["blocking_count"] == 0
    assert summary["high_impact_count"] == 4


def test_assertions_are_explicit(fixture, evaluation):
    report = evaluate_link_graph_foundation_frontier_assertions(fixture, evaluation)
    summary = assertion_summary(report)
    assert report.accepted
    assert summary["assertion_count"] == 7
    assert summary["passed_count"] == 7
    assert not report.failed_assertions


def test_export_manifest_is_json_safe(fixture, evaluation):
    manifest = build_link_graph_foundation_frontier_export_manifest(fixture, evaluation)
    payload = export_link_graph_foundation_frontier_manifest(manifest)
    assert manifest.accepted
    assert len(manifest.artifacts) == 2
    assert manifest.artifact("fixture-records").row_count == 16
    assert json.loads(json.dumps(payload))["accepted"] is True


def test_projection_diff_is_empty_for_same_snapshot(fixture):
    diff = compare_link_graph_foundation_frontier_fixture_to_self(fixture)
    assert diff.equal
    assert not diff.changed_record_ids
    assert diff.left_address == diff.right_address == fixture.content_address


def test_audit_trail_is_append_only(fixture, evaluation):
    trail = build_link_graph_foundation_frontier_audit_trail(fixture, evaluation)
    summary = audit_trail_summary(trail)
    assert trail.accepted
    assert trail.chain_valid
    assert len(trail.events) == 16
    assert summary["first_event"] == "event-001"
    assert summary["last_event"] == "event-016"
    assert trail.event("event-008").sequence == 8


def test_module_catalog_has_layered_surface():
    catalog = build_link_graph_foundation_frontier_module_catalog()
    summary = module_catalog_summary(catalog)
    assert catalog.accepted
    assert summary["module_count"] == 7
    assert summary["layer_count"] == 7
    assert all(catalog.by_layer(layer) for layer in catalog.layers)


def test_workflow_is_the_composed_release_path(fixture):
    report = run_link_graph_foundation_frontier_workflow(fixture)
    summary = workflow_summary(report)
    assert report.accepted
    assert summary["stage_count"] == 6
    assert summary["passed_count"] == 6
    assert summary["publishable"] is True
    assert not report.failed_stages


def test_review_packet_contains_all_review_surfaces(fixture):
    packet = build_link_graph_foundation_frontier_review_packet(fixture)
    summary = review_packet_summary(packet)
    assert packet.accepted
    assert summary["workflow_stages"] == 6
    assert summary["projection_rows"] == 16
    assert summary["audit_events"] == 16
    assert summary["catalog_entries"] == 7


def test_metrics_comparison_is_equal_to_itself(fixture, evaluation):
    from glio_noncode.link_graph_foundation_frontier_metrics import (
        build_link_graph_foundation_frontier_metrics,
    )

    metrics = build_link_graph_foundation_frontier_metrics(evaluation, fixture)
    comparison = compare_link_graph_foundation_frontier_metrics(metrics, metrics)
    assert metrics.accepted
    assert comparison["equal"] is True
    assert comparison["differences"] == {}


def test_all_depth_surfaces_serialize_without_runtime_types(fixture, evaluation):
    packet = build_link_graph_foundation_frontier_review_packet(fixture)
    payload = packet.to_dict()
    serialized = json.dumps(payload, sort_keys=True)
    assert serialized.startswith("{")
    assert "content_address" in payload
    assert payload["workflow"]["accepted"] is True
    assert payload["projection"]["row_count"] == 16
    assert payload["audit_trail"]["chain_valid"] is True
    assert payload["module_catalog"]["accepted"] is True
