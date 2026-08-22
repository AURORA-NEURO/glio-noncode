"""Deep tests for Domain 10 C01-C04 baseline links."""

from __future__ import annotations

import json

from glio_noncode.link_graph_foundation_frontier_accessibility import evaluate_link_graph_foundation_frontier_accessibility
from glio_noncode.link_graph_foundation_frontier_adapters import build_link_graph_foundation_frontier_adapters
from glio_noncode.link_graph_foundation_frontier_artifacts import build_link_graph_foundation_frontier_artifacts
from glio_noncode.link_graph_foundation_frontier_bundle import build_link_graph_foundation_frontier_bundle
from glio_noncode.link_graph_foundation_frontier_checks import run_link_graph_foundation_frontier_invariants
from glio_noncode.link_graph_foundation_frontier_cli import LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS, run_link_graph_foundation_frontier_operation
from glio_noncode.link_graph_foundation_frontier_contracts import build_link_graph_foundation_frontier_contracts
from glio_noncode.link_graph_foundation_frontier_depth import audit_link_graph_foundation_frontier_depth
from glio_noncode.link_graph_foundation_frontier_fixture_eval import evaluate_link_graph_foundation_frontier_fixture
from glio_noncode.link_graph_foundation_frontier_integrity import evaluate_link_graph_foundation_frontier_integrity
from glio_noncode.link_graph_foundation_frontier_lineage import build_link_graph_foundation_frontier_lineage, verify_link_graph_foundation_frontier_lineage
from glio_noncode.link_graph_foundation_frontier_metrics import build_link_graph_foundation_frontier_metrics
from glio_noncode.link_graph_foundation_frontier_pipeline import run_link_graph_foundation_frontier_pipeline
from glio_noncode.link_graph_foundation_frontier_policy import evaluate_link_graph_foundation_frontier_policy
from glio_noncode.link_graph_foundation_frontier_provenance import build_link_graph_foundation_frontier_provenance
from glio_noncode.link_graph_foundation_frontier_public_data import audit_link_graph_foundation_frontier_data, default_link_graph_foundation_frontier_fixture, link_graph_foundation_frontier_fixture_json
from glio_noncode.link_graph_foundation_frontier_quality_gate import build_link_graph_foundation_frontier_quality
from glio_noncode.link_graph_foundation_frontier_reconciliation import reconcile_link_graph_foundation_frontier
from glio_noncode.link_graph_foundation_frontier_replay import build_link_graph_foundation_frontier_expectations, replay_link_graph_foundation_frontier
from glio_noncode.link_graph_foundation_frontier_review_queue import build_link_graph_foundation_frontier_review_queue
from glio_noncode.link_graph_foundation_frontier_scenario_matrix import build_link_graph_foundation_frontier_scenario_matrix
from glio_noncode.link_graph_foundation_frontier_schema import validate_link_graph_foundation_frontier_schema
from glio_noncode.link_graph_foundation_frontier_source_registry import build_link_graph_foundation_frontier_source_registry
from glio_noncode.link_graph_foundation_frontier_validation_matrix import build_link_graph_foundation_frontier_validation_matrix
from glio_noncode.link_graph_foundation_frontier_views import build_link_graph_foundation_frontier_view, filter_link_graph_foundation_frontier_review_queue
from glio_noncode.link_graph_foundation_frontier_runtime import LinkGraphFoundationFrontierRuntimeOptions, run_link_graph_foundation_frontier_runtime


def test_fixture_shape_and_audit():
    fixture = default_link_graph_foundation_frontier_fixture()
    audit = audit_link_graph_foundation_frontier_data(fixture)
    assert audit.accepted
    assert (audit.record_count, audit.source_count, audit.positive_count, audit.control_count) == (16, 5, 4, 12)
    assert json.loads(link_graph_foundation_frontier_fixture_json(fixture))["fixture_id"] == fixture.fixture_id


def test_replay_all_operations():
    evaluation = evaluate_link_graph_foundation_frontier_fixture()
    assert evaluation.accepted
    assert (evaluation.state_match_count, evaluation.issue_match_count) == (16, 16)
    assert not evaluation.failed_record_ids
    assert evaluation.by_operation("coordinate_overlap")[1].observed_state == "ambiguous"
    assert evaluation.by_operation("nearest_gene")[2].observed_state == "abstained"
    assert evaluation.by_operation("ccre_assignment")[2].observed_state == "absent"
    assert evaluation.by_operation("enhancer_gene_consensus")[2].observed_state == "contradictory"


def test_adapter_registry_is_closed():
    registry = build_link_graph_foundation_frontier_adapters()
    assert registry.accepted
    assert len(registry.specs) == 4
    assert all(spec.input_fields and spec.output_fields and spec.limitation for spec in registry.specs)


def test_contract_source_and_schema():
    fixture = default_link_graph_foundation_frontier_fixture()
    evaluation = evaluate_link_graph_foundation_frontier_fixture(fixture)
    assert build_link_graph_foundation_frontier_contracts().accepted
    assert build_link_graph_foundation_frontier_source_registry(fixture).accepted
    schema = validate_link_graph_foundation_frontier_schema(fixture, evaluation)
    assert schema.accepted
    assert schema.field("context_key").required


def test_metrics_lineage_provenance():
    fixture = default_link_graph_foundation_frontier_fixture()
    evaluation = evaluate_link_graph_foundation_frontier_fixture(fixture)
    metrics = build_link_graph_foundation_frontier_metrics(evaluation, fixture)
    lineage = build_link_graph_foundation_frontier_lineage(fixture, evaluation)
    provenance = build_link_graph_foundation_frontier_provenance(fixture, evaluation)
    assert metrics.state_accuracy == 1.0
    assert verify_link_graph_foundation_frontier_lineage(lineage, fixture)
    assert provenance.accepted
    assert len(provenance.nodes) == 21


def test_policy_reconciliation_quality():
    fixture = default_link_graph_foundation_frontier_fixture()
    evaluation = evaluate_link_graph_foundation_frontier_fixture(fixture)
    policy = evaluate_link_graph_foundation_frontier_policy(evaluation)
    reconciliation = reconcile_link_graph_foundation_frontier(evaluation)
    quality = build_link_graph_foundation_frontier_quality(fixture, audit_link_graph_foundation_frontier_data(fixture), validate_link_graph_foundation_frontier_schema(fixture, evaluation), evaluation, reconciliation)
    assert policy.accepted
    assert reconciliation.accepted
    assert not reconciliation.mismatches
    assert quality.accepted


def test_depth_validation_scenarios_and_boundaries():
    fixture = default_link_graph_foundation_frontier_fixture()
    evaluation = evaluate_link_graph_foundation_frontier_fixture(fixture)
    assert audit_link_graph_foundation_frontier_depth(fixture, evaluation).accepted
    assert build_link_graph_foundation_frontier_validation_matrix(evaluation).accepted
    assert build_link_graph_foundation_frontier_scenario_matrix(evaluation).accepted
    assert evaluate_link_graph_foundation_frontier_accessibility(fixture, evaluation).accepted
    assert run_link_graph_foundation_frontier_invariants(fixture, evaluation).accepted
    assert evaluate_link_graph_foundation_frontier_integrity(fixture, evaluation).accepted


def test_release_bundle_artifacts_and_replay():
    pipeline = run_link_graph_foundation_frontier_pipeline()
    assert pipeline.accepted
    assert pipeline.release.publishable
    assert pipeline.bundle.accepted
    assert pipeline.artifacts.accepted
    assert replay_link_graph_foundation_frontier(pipeline.evaluation, build_link_graph_foundation_frontier_expectations(pipeline.evaluation)).accepted


def test_review_view_and_runtime():
    pipeline = run_link_graph_foundation_frontier_pipeline()
    queue = build_link_graph_foundation_frontier_review_queue(pipeline.evaluation, pipeline.policy)
    view = build_link_graph_foundation_frontier_view(pipeline.fixture, pipeline.evaluation, queue)
    assert queue.accepted
    assert view.accepted
    assert len(filter_link_graph_foundation_frontier_review_queue(queue, operation="nearest_gene")) == 4
    assert run_link_graph_foundation_frontier_runtime(LinkGraphFoundationFrontierRuntimeOptions(include_payload=False)).accepted


def test_pipeline_has_twelve_stages():
    pipeline = run_link_graph_foundation_frontier_pipeline()
    assert len(pipeline.stages) == 12
    assert all(stage.status == "passed" for stage in pipeline.stages)
    assert not pipeline.failed_stages


def test_cli_commands_are_json_safe():
    for command in LINK_GRAPH_FOUNDATION_FRONTIER_COMMANDS:
        value = run_link_graph_foundation_frontier_operation(command)
        assert isinstance(value, dict)
        json.dumps(value)
    summary = run_link_graph_foundation_frontier_operation("link-graph-foundation-frontier-summary")
    assert summary["record_count"] == 16
    assert summary["source_count"] == 5
    assert summary["accepted"] is True
