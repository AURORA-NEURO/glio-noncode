"""Deep contract tests for Domain 10 C09-C12 link paths."""

from __future__ import annotations

import json

import pytest

from glio_noncode.link_graph_alpha_frontier_accessibility import evaluate_link_graph_alpha_frontier_accessibility
from glio_noncode.link_graph_alpha_frontier_acceptance import evaluate_link_graph_alpha_frontier_acceptance
from glio_noncode.link_graph_alpha_frontier_adapters import build_link_graph_alpha_frontier_adapters, execute_link_graph_alpha_frontier_record
from glio_noncode.link_graph_alpha_frontier_artifacts import build_link_graph_alpha_frontier_artifacts
from glio_noncode.link_graph_alpha_frontier_assurance import build_link_graph_alpha_frontier_assurance
from glio_noncode.link_graph_alpha_frontier_benchmark import benchmark_link_graph_alpha_frontier
from glio_noncode.link_graph_alpha_frontier_bundle import build_link_graph_alpha_frontier_bundle
from glio_noncode.link_graph_alpha_frontier_candidate_depth import audit_link_graph_alpha_frontier_candidates
from glio_noncode.link_graph_alpha_frontier_catalog import build_link_graph_alpha_frontier_catalog
from glio_noncode.link_graph_alpha_frontier_checks import run_link_graph_alpha_frontier_invariants
from glio_noncode.link_graph_alpha_frontier_claim_boundary import allowed_link_graph_alpha_frontier_claims, build_link_graph_alpha_frontier_claim_boundary
from glio_noncode.link_graph_alpha_frontier_comparison import compare_link_graph_alpha_frontier_runs
from glio_noncode.link_graph_alpha_frontier_compliance import evaluate_link_graph_alpha_frontier_boundary
from glio_noncode.link_graph_alpha_frontier_conformance import build_link_graph_alpha_frontier_conformance
from glio_noncode.link_graph_alpha_frontier_control_catalog import build_link_graph_alpha_frontier_control_catalog
from glio_noncode.link_graph_alpha_frontier_contracts import build_link_graph_alpha_frontier_contracts
from glio_noncode.link_graph_alpha_frontier_data_dictionary import build_link_graph_alpha_frontier_data_dictionary
from glio_noncode.link_graph_alpha_frontier_delta_depth import audit_link_graph_alpha_frontier_deltas
from glio_noncode.link_graph_alpha_frontier_depth import audit_link_graph_alpha_frontier_depth
from glio_noncode.link_graph_alpha_frontier_evidence_matrix import build_link_graph_alpha_frontier_evidence_matrix
from glio_noncode.link_graph_alpha_frontier_exports import export_link_graph_alpha_frontier_review_csv, render_link_graph_alpha_frontier_review_markdown
from glio_noncode.link_graph_alpha_frontier_failure_catalog import build_link_graph_alpha_frontier_failure_catalog
from glio_noncode.link_graph_alpha_frontier_fixture_eval import evaluate_link_graph_alpha_frontier_fixture
from glio_noncode.link_graph_alpha_frontier_history import build_link_graph_alpha_frontier_history
from glio_noncode.link_graph_alpha_frontier_integrity import evaluate_link_graph_alpha_frontier_integrity
from glio_noncode.link_graph_alpha_frontier_lineage import build_link_graph_alpha_frontier_lineage, verify_link_graph_alpha_frontier_lineage
from glio_noncode.link_graph_alpha_frontier_metrics import build_link_graph_alpha_frontier_metrics
from glio_noncode.link_graph_alpha_frontier_observability import build_link_graph_alpha_frontier_trace, link_graph_alpha_frontier_review_budget
from glio_noncode.link_graph_alpha_frontier_operator_handbook import build_link_graph_alpha_frontier_handbook
from glio_noncode.link_graph_alpha_frontier_packaging import build_link_graph_alpha_frontier_package_manifest, serialize_link_graph_alpha_frontier_package_manifest
from glio_noncode.link_graph_alpha_frontier_pipeline import run_link_graph_alpha_frontier_pipeline
from glio_noncode.link_graph_alpha_frontier_policy import LinkGraphAlphaFrontierDisposition, evaluate_link_graph_alpha_frontier_policy
from glio_noncode.link_graph_alpha_frontier_provenance import build_link_graph_alpha_frontier_provenance
from glio_noncode.link_graph_alpha_frontier_public_data import (
    LINK_GRAPH_ALPHA_FRONTIER_BOUNDARY,
    LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY,
    LINK_GRAPH_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY,
    LinkGraphAlphaFrontierOperation,
    LinkGraphAlphaFrontierRole,
    audit_link_graph_alpha_frontier_data,
    default_link_graph_alpha_frontier_fixture,
    fixture_json,
)
from glio_noncode.link_graph_alpha_frontier_query_plan import build_link_graph_alpha_frontier_query_plans
from glio_noncode.link_graph_alpha_frontier_queries import query_link_graph_alpha_frontier_records, query_link_graph_alpha_frontier_results
from glio_noncode.link_graph_alpha_frontier_reconciliation import reconcile_link_graph_alpha_frontier
from glio_noncode.link_graph_alpha_frontier_regression import run_link_graph_alpha_frontier_regression
from glio_noncode.link_graph_alpha_frontier_release_notes import build_link_graph_alpha_frontier_release_notes
from glio_noncode.link_graph_alpha_frontier_replay import build_link_graph_alpha_frontier_expectations, replay_link_graph_alpha_frontier_evaluation
from glio_noncode.link_graph_alpha_frontier_report_render import render_link_graph_alpha_frontier_pipeline_markdown, render_link_graph_alpha_frontier_stage_lines
from glio_noncode.link_graph_alpha_frontier_resource_limits import default_link_graph_alpha_frontier_resource_limits
from glio_noncode.link_graph_alpha_frontier_review_queue import build_link_graph_alpha_frontier_review_queue
from glio_noncode.link_graph_alpha_frontier_runbook import build_link_graph_alpha_frontier_runbook
from glio_noncode.link_graph_alpha_frontier_runtime import LinkGraphAlphaFrontierRuntimeOptions, run_link_graph_alpha_frontier_runtime
from glio_noncode.link_graph_alpha_frontier_scenario_matrix import build_link_graph_alpha_frontier_scenario_matrix
from glio_noncode.link_graph_alpha_frontier_schema import link_graph_alpha_frontier_schema_manifest, validate_link_graph_alpha_frontier_schema
from glio_noncode.link_graph_alpha_frontier_scorecard import build_link_graph_alpha_frontier_scorecard
from glio_noncode.link_graph_alpha_frontier_source_checks import run_link_graph_alpha_frontier_source_checks
from glio_noncode.link_graph_alpha_frontier_source_registry import build_link_graph_alpha_frontier_source_registry
from glio_noncode.link_graph_alpha_frontier_state_transitions import build_link_graph_alpha_frontier_state_transitions
from glio_noncode.link_graph_alpha_frontier_thresholds import default_link_graph_alpha_frontier_thresholds
from glio_noncode.link_graph_alpha_frontier_validation_matrix import build_link_graph_alpha_frontier_validation_matrix
from glio_noncode.link_graph_alpha_frontier_validation_report import build_link_graph_alpha_frontier_validation_report
from glio_noncode.link_graph_alpha_frontier_views import build_link_graph_alpha_frontier_view, filter_link_graph_alpha_frontier_review_queue, link_graph_alpha_frontier_review_summary
from glio_noncode.link_graph_alpha_frontier_manifest_serialization import deserialize_link_graph_alpha_frontier_manifest, round_trip_link_graph_alpha_frontier_manifest, serialize_link_graph_alpha_frontier_manifest


@pytest.fixture()
def fixture():
    return default_link_graph_alpha_frontier_fixture()


@pytest.fixture()
def evaluation(fixture):
    return evaluate_link_graph_alpha_frontier_fixture(fixture)


def test_fixture_has_balanced_public_boundary(fixture):
    audit = audit_link_graph_alpha_frontier_data(fixture)
    assert audit.accepted
    assert audit.record_count == 16
    assert audit.source_count == 5
    assert audit.positive_count == 4
    assert audit.control_count == 12
    assert fixture.boundary == LINK_GRAPH_ALPHA_FRONTIER_BOUNDARY
    assert {record.context_key for record in fixture.records if record.record_id.endswith("C3")} == {LINK_GRAPH_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY}


def test_fixture_has_four_operations_and_roles(fixture):
    assert all(len(fixture.operation_records(operation)) == 4 for operation in LinkGraphAlphaFrontierOperation)
    assert all(len(tuple(item for item in fixture.operation_records(operation) if item.role is LinkGraphAlphaFrontierRole.POSITIVE)) == 1 for operation in LinkGraphAlphaFrontierOperation)
    assert fixture.operation_records("crispr_perturbation")[0].payload["observations"]


def test_fixture_json_is_canonical(fixture):
    payload = fixture_json(fixture)
    assert json.loads(payload)["fixture_id"] == fixture.fixture_id
    assert payload == fixture_json(fixture)


def test_replay_matches_all_states_and_issues(evaluation):
    assert evaluation.accepted
    assert evaluation.state_match_count == 16
    assert evaluation.issue_match_count == 16
    assert not evaluation.failed_record_ids
    assert len(evaluation.by_state("out_of_domain")) == 4


def test_replay_exposes_expected_operation_boundaries(evaluation):
    assert evaluation.by_operation("crispr_perturbation")[2].observed_state == "contradictory"
    assert evaluation.by_operation("contact_3d")[2].observed_issue_codes == ("single_assay", "alternative_gene") or set(evaluation.by_operation("contact_3d")[2].observed_issue_codes) == {"single_assay", "alternative_gene"}
    assert evaluation.by_operation("promoter_tethering")[1].observed_state == "abstained"
    assert evaluation.by_operation("multi_gene_graph")[2].observed_state == "contradictory"


def test_adapters_cover_all_operations(fixture):
    registry = build_link_graph_alpha_frontier_adapters()
    assert registry.accepted
    assert len(registry.specs) == 4
    assert {spec.operation for spec in registry.specs} == set(LinkGraphAlphaFrontierOperation)
    assert all(execute_link_graph_alpha_frontier_record(record).content_address.startswith("sha256:") for record in fixture.records)


def test_contracts_and_schema_are_closed(fixture, evaluation):
    contracts = build_link_graph_alpha_frontier_contracts()
    schema = validate_link_graph_alpha_frontier_schema(fixture, evaluation)
    assert contracts.accepted
    assert schema.accepted
    assert len(contracts.contracts) == 4
    assert schema.field("context_key").required
    assert len(link_graph_alpha_frontier_schema_manifest()["fields"]) == 9


def test_source_registry_and_source_checks_are_closed(fixture):
    registry = build_link_graph_alpha_frontier_source_registry(fixture)
    assert registry.accepted
    assert run_link_graph_alpha_frontier_source_checks(fixture).accepted
    assert set(item.source.source_id for item in registry.entries) == {item.source_id for item in fixture.sources}


def test_metrics_are_one_hundred_percent(evaluation, fixture):
    metrics = build_link_graph_alpha_frontier_metrics(evaluation, fixture)
    assert metrics.accepted
    assert metrics.state_accuracy == 1.0
    assert metrics.issue_accuracy == 1.0
    assert metrics.for_operation("promoter_tethering").record_count == 4


def test_lineage_and_provenance_cover_every_record(fixture, evaluation):
    lineage = build_link_graph_alpha_frontier_lineage(fixture, evaluation)
    provenance = build_link_graph_alpha_frontier_provenance(fixture, evaluation)
    assert verify_link_graph_alpha_frontier_lineage(lineage, fixture)
    assert provenance.accepted
    assert len(lineage.record_ids) == 16
    assert len(provenance.nodes) == 21


def test_policy_routes_context_to_abstention(evaluation):
    policy = evaluate_link_graph_alpha_frontier_policy(evaluation)
    assert policy.accepted
    assert all(policy.decision_for(row.record_id).disposition is not LinkGraphAlphaFrontierDisposition.RELEASE for row in evaluation.rows if row.record_id.endswith("C3"))


def test_reconciliation_and_quality_pass(fixture, evaluation):
    reconciliation = reconcile_link_graph_alpha_frontier(evaluation)
    quality = __import__("glio_noncode.link_graph_alpha_frontier_quality_gate", fromlist=["build_link_graph_alpha_frontier_quality"]).build_link_graph_alpha_frontier_quality(fixture, audit_link_graph_alpha_frontier_data(fixture), validate_link_graph_alpha_frontier_schema(fixture, evaluation), evaluation, reconciliation)
    assert reconciliation.accepted
    assert quality.accepted
    assert not reconciliation.mismatches


def test_depth_candidate_delta_matrix_scenarios_pass(fixture, evaluation):
    assert audit_link_graph_alpha_frontier_depth(fixture, evaluation).accepted
    assert audit_link_graph_alpha_frontier_candidates(evaluation).accepted
    assert audit_link_graph_alpha_frontier_deltas(fixture, evaluation).accepted
    assert build_link_graph_alpha_frontier_validation_matrix(evaluation).accepted
    assert build_link_graph_alpha_frontier_scenario_matrix(evaluation).accepted


def test_boundary_and_integrity_pass(fixture, evaluation):
    assert evaluate_link_graph_alpha_frontier_accessibility(fixture, evaluation).accepted
    assert evaluate_link_graph_alpha_frontier_boundary(fixture, evaluation).accepted
    assert evaluate_link_graph_alpha_frontier_integrity(fixture, evaluation).accepted
    assert run_link_graph_alpha_frontier_invariants(fixture, evaluation).accepted


def test_review_queue_and_view_are_complete(fixture, evaluation):
    queue = build_link_graph_alpha_frontier_review_queue(evaluation, evaluate_link_graph_alpha_frontier_policy(evaluation))
    view = build_link_graph_alpha_frontier_view(fixture, evaluation, queue)
    assert queue.accepted
    assert view.accepted
    assert len(filter_link_graph_alpha_frontier_review_queue(queue, operation="contact_3d")) == 4
    assert link_graph_alpha_frontier_review_summary(queue)["entry_count"] == 16


def test_release_bundle_artifacts_and_runtime_pass():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    assert pipeline.accepted
    assert pipeline.release.publishable
    assert build_link_graph_alpha_frontier_bundle(pipeline.fixture, pipeline.release, pipeline.metrics, pipeline.deltas).accepted
    assert build_link_graph_alpha_frontier_artifacts(pipeline.bundle, pipeline.evaluation).accepted
    assert evaluate_link_graph_alpha_frontier_acceptance(pipeline).accepted
    runtime = run_link_graph_alpha_frontier_runtime(LinkGraphAlphaFrontierRuntimeOptions(include_payload=False))
    assert runtime.accepted
    assert runtime.pipeline is None


def test_pipeline_has_twelve_passing_stages():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    assert len(pipeline.stages) == 12
    assert not pipeline.failed_stages
    assert all(item.status == "passed" for item in pipeline.stages)


def test_observability_and_rendering():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    trace = build_link_graph_alpha_frontier_trace(pipeline.evaluation, "test-run")
    assert trace.accepted
    assert link_graph_alpha_frontier_review_budget(trace)["within_budget"]
    assert len(render_link_graph_alpha_frontier_stage_lines(pipeline)) == 12
    assert "Stages" in render_link_graph_alpha_frontier_pipeline_markdown(pipeline)


def test_replay_expectations_are_addressed(evaluation):
    expectations = build_link_graph_alpha_frontier_expectations(evaluation)
    replay = replay_link_graph_alpha_frontier_evaluation(evaluation, expectations)
    assert replay.accepted
    assert len(replay.expectations) == 16


def test_export_formats_are_stable():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    csv_text = export_link_graph_alpha_frontier_review_csv(pipeline.review_queue)
    markdown = render_link_graph_alpha_frontier_review_markdown(pipeline.review_queue)
    assert csv_text.startswith("record_id,operation")
    assert "| Record | Operation |" in markdown


def test_catalogs_and_boundaries():
    fixture = default_link_graph_alpha_frontier_fixture()
    assert build_link_graph_alpha_frontier_catalog().accepted
    assert build_link_graph_alpha_frontier_control_catalog(fixture).accepted
    assert build_link_graph_alpha_frontier_data_dictionary().accepted
    boundary = build_link_graph_alpha_frontier_claim_boundary()
    assert boundary.accepted
    assert allowed_link_graph_alpha_frontier_claims("contact_3d") == ("candidate evidence path is present",)


def test_failure_catalog_and_assurance():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    failure = build_link_graph_alpha_frontier_failure_catalog(pipeline.evaluation)
    evidence = build_link_graph_alpha_frontier_evidence_matrix(pipeline.evaluation)
    conformance = build_link_graph_alpha_frontier_conformance(pipeline.contracts, build_link_graph_alpha_frontier_adapters(), pipeline.evaluation)
    assert failure.accepted
    assert evidence.accepted
    assert conformance.accepted
    assert build_link_graph_alpha_frontier_assurance(conformance, evidence, failure).accepted


def test_governance_history_packaging_and_notes():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    governance = __import__("glio_noncode.link_graph_alpha_frontier_governance", fromlist=["build_link_graph_alpha_frontier_governance"]).build_link_graph_alpha_frontier_governance()
    history = build_link_graph_alpha_frontier_history()
    package = build_link_graph_alpha_frontier_package_manifest(pipeline.bundle)
    notes = build_link_graph_alpha_frontier_release_notes(pipeline.release)
    handbook = build_link_graph_alpha_frontier_handbook(build_link_graph_alpha_frontier_runbook())
    assert governance.accepted
    assert history.latest().fixture_version == pipeline.fixture.version
    assert package.accepted
    assert "Limitations" in notes.to_markdown()
    assert handbook.runbook_address.startswith("sha256:")


def test_audit_scorecard_and_transitions():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    audit = __import__("glio_noncode.link_graph_alpha_frontier_audit_log", fromlist=["build_link_graph_alpha_frontier_audit_log"]).build_link_graph_alpha_frontier_audit_log(pipeline)
    scorecard = build_link_graph_alpha_frontier_scorecard(pipeline.metrics, pipeline.quality)
    transitions = build_link_graph_alpha_frontier_state_transitions(pipeline.evaluation)
    assert audit.accepted
    assert scorecard.accepted
    assert transitions.accepted


def test_query_plans_and_queries(fixture, evaluation):
    plans = build_link_graph_alpha_frontier_query_plans()
    assert plans.accepted
    assert len(query_link_graph_alpha_frontier_records(fixture, role="control")) == 12
    assert len(query_link_graph_alpha_frontier_results(evaluation, state="out_of_domain")) == 4


def test_serialization_round_trip():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    manifest = pipeline.release
    payload = serialize_link_graph_alpha_frontier_manifest(manifest)
    assert deserialize_link_graph_alpha_frontier_manifest(payload)["release_id"] == manifest.release_id
    assert round_trip_link_graph_alpha_frontier_manifest(manifest)
    assert serialize_link_graph_alpha_frontier_package_manifest(build_link_graph_alpha_frontier_package_manifest(pipeline.bundle))


def test_thresholds_resources_regression_and_validation_report():
    pipeline = run_link_graph_alpha_frontier_pipeline()
    assert default_link_graph_alpha_frontier_thresholds().accepted
    limits = default_link_graph_alpha_frontier_resource_limits()
    assert limits.within(records=16, sources=5, events=12, seconds=1.0)
    assert run_link_graph_alpha_frontier_regression(pipeline.fixture, pipeline.evaluation).accepted
    assert build_link_graph_alpha_frontier_validation_report(pipeline).accepted


def test_comparison_is_stable():
    left = run_link_graph_alpha_frontier_pipeline(run_id="left")
    right = run_link_graph_alpha_frontier_pipeline(run_id="right")
    comparison = compare_link_graph_alpha_frontier_runs(left, right)
    assert comparison.accepted
    assert comparison.same_fixture
    assert comparison.same_evaluation


def test_benchmark_rejects_non_positive_iterations():
    with pytest.raises(ValueError):
        benchmark_link_graph_alpha_frontier(0)
    result = benchmark_link_graph_alpha_frontier(1)
    assert result.accepted_iterations == 1
    assert result.records_processed == 16
