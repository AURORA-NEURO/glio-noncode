"""Deep contract tests for Domain 11 C01-C04 causal foundations."""

from __future__ import annotations

import csv
import io
import json

import pytest

from glio_noncode.causal_foundation_frontier_adapters import (
    build_causal_foundation_frontier_adapters,
    execute_causal_foundation_frontier_record,
)
from glio_noncode.causal_foundation_frontier_artifacts import (
    CausalFoundationFrontierArtifactKind,
)
from glio_noncode.causal_foundation_frontier_contracts import (
    build_causal_foundation_frontier_contracts,
)
from glio_noncode.causal_foundation_frontier_fixture_eval import (
    evaluate_causal_foundation_frontier_fixture,
)
from glio_noncode.causal_foundation_frontier_integrity import (
    evaluate_causal_foundation_frontier_integrity,
)
from glio_noncode.causal_foundation_frontier_lineage import (
    build_causal_foundation_frontier_lineage,
    verify_causal_foundation_frontier_lineage,
)
from glio_noncode.causal_foundation_frontier_metrics import (
    build_causal_foundation_frontier_metrics,
)
from glio_noncode.causal_foundation_frontier_policy import (
    CausalFoundationFrontierDecision,
    default_causal_foundation_frontier_policy,
)
from glio_noncode.causal_foundation_frontier_provenance import (
    build_causal_foundation_frontier_provenance,
)
from glio_noncode.causal_foundation_frontier_public_data import (
    CAUSAL_FOUNDATION_FRONTIER_BOUNDARY,
    CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY,
    CAUSAL_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY,
    CausalFoundationFrontierOperation,
    CausalFoundationFrontierRole,
    audit_causal_foundation_frontier_data,
    causal_foundation_frontier_fixture_json,
    default_causal_foundation_frontier_fixture,
)
from glio_noncode.causal_foundation_frontier_reconciliation import (
    reconcile_causal_foundation_frontier,
)
from glio_noncode.causal_foundation_frontier_replay import (
    replay_causal_foundation_frontier,
    replay_is_deterministic,
)
from glio_noncode.causal_foundation_frontier_review import (
    build_causal_foundation_frontier_review_queue,
)
from glio_noncode.causal_foundation_frontier_scenario_matrix import (
    build_causal_foundation_frontier_scenario_matrix,
)
from glio_noncode.causal_foundation_frontier_schema import (
    default_causal_foundation_frontier_fields,
    validate_causal_foundation_frontier_schema,
)
from glio_noncode.causal_foundation_frontier_validation_matrix import (
    build_causal_foundation_frontier_validation_matrix,
)
from glio_noncode.causal_foundation_frontier_views import (
    build_causal_foundation_frontier_review_view,
    build_causal_foundation_frontier_summary_view,
)


@pytest.fixture(scope="module")
def fixture():
    return default_causal_foundation_frontier_fixture()


@pytest.fixture(scope="module")
def evaluation(fixture):
    return evaluate_causal_foundation_frontier_fixture(fixture)


def test_fixture_declares_boundary_and_contexts(fixture):
    assert fixture.boundary == CAUSAL_FOUNDATION_FRONTIER_BOUNDARY
    assert fixture.context_key == CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY
    assert fixture.foreign_context_key == CAUSAL_FOUNDATION_FRONTIER_FOREIGN_CONTEXT_KEY
    assert fixture.fixture_id.startswith("causal-foundation-frontier-")


def test_fixture_has_closed_source_and_record_counts(fixture):
    assert len(fixture.sources) == 5
    assert len(fixture.records) == 16
    assert len(fixture.positive_records) == 4
    assert len(fixture.control_records) == 12
    assert {item.operation for item in fixture.records} == set(CausalFoundationFrontierOperation)


def test_source_receipts_are_public_https_records(fixture):
    assert all(item.uri.startswith("https://") for item in fixture.sources)
    assert all(item.source_kind.startswith("public_") for item in fixture.sources)
    assert len({item.content_address for item in fixture.sources}) == len(fixture.sources)
    assert {"encode", "four-d", "geo", "gtex", "pubmed"} == set(fixture.source_map())


def test_data_audit_is_closed(fixture):
    audit = audit_causal_foundation_frontier_data(fixture)
    assert audit.accepted
    assert audit.failed_checks == ()
    assert audit.record_count == 16
    assert audit.source_count == 5
    assert audit.foreign_context_count == 4
    assert all(item["content_address"].startswith("sha256:") for item in audit.checks)


@pytest.mark.parametrize(
    ("operation", "capability"),
    [
        (CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, "GNC-D11-C01"),
        (CausalFoundationFrontierOperation.FACTOR_GRAPH, "GNC-D11-C02"),
        (CausalFoundationFrontierOperation.CONTEXT_PRIOR, "GNC-D11-C03"),
        (CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, "GNC-D11-C04"),
    ],
)
def test_each_operation_has_one_positive_and_three_controls(fixture, operation, capability):
    rows = fixture.operation_records(operation)
    assert len(rows) == 4
    assert sum(item.role is CausalFoundationFrontierRole.POSITIVE for item in rows) == 1
    assert sum(item.role is CausalFoundationFrontierRole.CONTROL for item in rows) == 3
    assert capability in {"GNC-D11-C01", "GNC-D11-C02", "GNC-D11-C03", "GNC-D11-C04"}


def test_all_records_have_receipts_and_payloads(fixture):
    assert all(item.source_ids for item in fixture.records)
    assert all(item.payload for item in fixture.records)
    assert all(item.description for item in fixture.records)
    assert all(item.content_address.startswith("sha256:") for item in fixture.records)
    assert len(fixture.record_map()) == len(fixture.records)


def test_evaluation_is_exact(evaluation):
    assert evaluation.accepted
    assert evaluation.state_match_count == 16
    assert evaluation.issue_match_count == 16
    assert evaluation.failed_record_ids == ()
    assert evaluation.state_counts == {
        "abstained": 2,
        "contradictory": 3,
        "out_of_domain": 5,
        "partial": 2,
        "supported": 4,
    }


def test_evaluation_issue_counts_are_explicit(evaluation):
    assert evaluation.issue_counts == {
        "context_mismatch": 4,
        "contradictory_factor_edge": 2,
        "contradictory_measurement": 1,
        "missing_prior_feature": 2,
        "orphan_factor_lineage": 1,
        "prior_feature_out_of_range": 1,
        "single_measurement_group": 1,
    }


@pytest.mark.parametrize(
    ("record_id", "state", "issues"),
    [
        ("D11-C01-P", "supported", ()),
        ("D11-C01-C1", "abstained", ("missing_prior_feature",)),
        ("D11-C01-C2", "contradictory", ("contradictory_factor_edge",)),
        ("D11-C01-C3", "out_of_domain", ("context_mismatch",)),
        ("D11-C02-P", "supported", ()),
        ("D11-C02-C1", "partial", ("orphan_factor_lineage",)),
        ("D11-C02-C2", "contradictory", ("contradictory_factor_edge",)),
        ("D11-C02-C3", "out_of_domain", ("context_mismatch",)),
        ("D11-C03-P", "supported", ()),
        ("D11-C03-C1", "abstained", ("missing_prior_feature",)),
        ("D11-C03-C2", "out_of_domain", ("prior_feature_out_of_range",)),
        ("D11-C03-C3", "out_of_domain", ("context_mismatch",)),
        ("D11-C04-P", "supported", ()),
        ("D11-C04-C1", "partial", ("single_measurement_group",)),
        ("D11-C04-C2", "contradictory", ("contradictory_measurement",)),
        ("D11-C04-C3", "out_of_domain", ("context_mismatch",)),
    ],
)
def test_each_fixture_record_replays_to_its_declared_floor(fixture, record_id, state, issues):
    record = fixture.record_map()[record_id]
    result = execute_causal_foundation_frontier_record(record)
    assert result.state.value == state
    assert result.issue_codes == issues
    assert result.record_id == record_id
    assert result.content_address.startswith("sha256:")
    assert result.source_ids == record.source_ids


def test_adapter_registry_is_closed():
    registry = build_causal_foundation_frontier_adapters()
    assert registry.accepted
    assert len(registry.specs) == 4
    assert {item.operation for item in registry.specs} == set(CausalFoundationFrontierOperation)
    assert all(item.output_fields for item in registry.specs)
    assert all(item.limitation for item in registry.specs)


def test_contract_report_is_closed():
    report = build_causal_foundation_frontier_contracts()
    assert report.accepted
    assert len(report.contracts) == 4
    assert {item.capability_id for item in report.contracts} == {"GNC-D11-C01", "GNC-D11-C02", "GNC-D11-C03", "GNC-D11-C04"}
    assert all(item.required_fields for item in report.contracts)
    assert all(item.output_fields for item in report.contracts)
    assert all(item.issue_codes for item in report.contracts)


def test_schema_report_aligns_with_evaluation(fixture, evaluation):
    report = validate_causal_foundation_frontier_schema(fixture, evaluation)
    assert report.accepted
    assert report.failed_checks == ()
    assert len(report.fields) == 10
    assert report.field("record_id").required
    assert report.field("expected_issue_codes").value_type == "array[string]"


def test_metrics_are_exact(fixture, evaluation):
    metrics = build_causal_foundation_frontier_metrics(evaluation, fixture)
    assert metrics.accepted
    assert metrics.record_count == 16
    assert metrics.positive_count == 4
    assert metrics.control_count == 12
    assert metrics.state_accuracy == 1.0
    assert metrics.issue_accuracy == 1.0
    assert all(item.accepted for item in metrics.operations)
    assert all(item.record_count == 4 for item in metrics.operations)


def test_policy_retains_only_supported_positive_rows(evaluation):
    policy = default_causal_foundation_frontier_policy()
    decisions = policy.decide(evaluation)
    assert len(decisions) == 16
    retained = [item for item in decisions if item.decision is CausalFoundationFrontierDecision.RETAIN]
    assert [item.record_id for item in retained] == ["D11-C01-P", "D11-C02-P", "D11-C03-P", "D11-C04-P"]
    assert all(item.publishable for item in retained)
    assert sum(item.decision is CausalFoundationFrontierDecision.QUARANTINE for item in decisions) == 8
    assert sum(item.decision is CausalFoundationFrontierDecision.ABSTAIN for item in decisions) == 2
    assert sum(item.decision is CausalFoundationFrontierDecision.REVIEW for item in decisions) == 2


def test_policy_rule_addresses_are_unique():
    policy = default_causal_foundation_frontier_policy()
    assert len(policy.rule_map()) == len(policy.rules)
    assert len({item.content_address for item in policy.rules}) == len(policy.rules)
    assert policy.content_address.startswith("sha256:")


def test_reconciliation_is_exact(fixture, evaluation):
    policy = default_causal_foundation_frontier_policy()
    decisions = policy.decide(evaluation)
    reconciliation = reconcile_causal_foundation_frontier(fixture, evaluation, decisions, policy)
    assert reconciliation.reconciled
    assert reconciliation.state_match_count == 16
    assert reconciliation.issue_match_count == 16
    assert reconciliation.mismatch_record_ids == ()
    assert reconciliation.accepted_count == 8
    assert reconciliation.review_count == 4
    assert reconciliation.quarantine_count == 8


def test_lineage_and_provenance_cover_all_records(fixture, evaluation):
    lineage = build_causal_foundation_frontier_lineage(fixture, evaluation)
    provenance = build_causal_foundation_frontier_provenance(fixture, evaluation)
    assert lineage.accepted
    assert verify_causal_foundation_frontier_lineage(lineage, fixture)
    assert len(lineage.fixture_edges) == 16
    assert len(lineage.record_edges) == 16
    assert len(lineage.source_edges) >= 16
    assert provenance.accepted
    assert provenance.orphan_node_ids == ()
    assert len(provenance.nodes) == 1 + len(fixture.sources) + len(fixture.records) + len(evaluation.rows)


def test_replay_is_deterministic(fixture):
    receipt = replay_causal_foundation_frontier(fixture)
    assert receipt.accepted
    assert receipt.deterministic
    assert receipt.row_count == 16
    assert receipt.first_address == receipt.second_address
    assert replay_is_deterministic(fixture)


def test_review_queue_retains_control_visibility(evaluation):
    queue = build_causal_foundation_frontier_review_queue(evaluation)
    assert queue.accepted
    assert len(queue.items) == 16
    assert queue.retained_count == 4
    assert queue.review_count == 4
    assert queue.blocked_count == 10
    assert set(queue.blocking_record_ids) >= {"D11-C01-C2", "D11-C01-C3", "D11-C03-C2", "D11-C04-C2"}
    assert len(queue.for_priority("critical")) == 8


def test_scenario_matrix_closes_four_operations(fixture, evaluation):
    matrix = build_causal_foundation_frontier_scenario_matrix(fixture, evaluation)
    assert matrix.accepted
    assert matrix.operation_count == 4
    assert matrix.scenario_count >= 12
    assert set(matrix.control_kinds) == {"positive", "missing", "contradictory", "foreign_context"}
    assert all(matrix.for_operation(operation.value) for operation in CausalFoundationFrontierOperation)


def test_validation_matrix_maps_capabilities(fixture, evaluation):
    matrix = build_causal_foundation_frontier_validation_matrix(fixture, evaluation)
    assert matrix.accepted
    assert matrix.cell_count == 16
    assert matrix.passed_count == 16
    assert matrix.failed_cells == ()
    assert {item.capability_id for item in matrix.cells} == {"GNC-D11-C01", "GNC-D11-C02", "GNC-D11-C03", "GNC-D11-C04"}
    assert len(matrix.for_scenario("foreign_context")) == 4


def test_review_view_has_stable_csv(fixture, evaluation):
    policy = default_causal_foundation_frontier_policy()
    decisions = policy.decide(evaluation)
    reconciliation = reconcile_causal_foundation_frontier(fixture, evaluation, decisions, policy)
    queue = build_causal_foundation_frontier_review_queue(evaluation, policy)
    view = build_causal_foundation_frontier_review_view(fixture, evaluation, decisions, reconciliation, queue)
    parsed = list(csv.DictReader(io.StringIO(view.to_csv())))
    assert len(parsed) == 16
    assert parsed[0]["record_id"] == "D11-C01-P"
    assert parsed[0]["decision"] == "retain"
    assert parsed[-1]["record_id"] == "D11-C04-C3"
    assert view.content_address.startswith("sha256:")


def test_summary_view_orders_issue_counts(fixture, evaluation):
    metrics = build_causal_foundation_frontier_metrics(evaluation, fixture)
    queue = build_causal_foundation_frontier_review_queue(evaluation)
    summary = build_causal_foundation_frontier_summary_view(fixture, metrics, queue, True)
    assert summary.accepted
    assert summary.retained_count == 4
    assert summary.quarantine_count == 10
    assert summary.top_issue_codes[0] == ("context_mismatch", 4)
    assert summary.content_address.startswith("sha256:")


def test_integrity_report_is_closed(fixture, evaluation):
    lineage = build_causal_foundation_frontier_lineage(fixture, evaluation)
    provenance = build_causal_foundation_frontier_provenance(fixture, evaluation)
    report = evaluate_causal_foundation_frontier_integrity(fixture, evaluation, lineage, provenance)
    assert report.accepted
    assert report.failed_check_ids == ()
    assert len(report.checks) == 8


def test_fixture_json_is_parseable(fixture):
    value = json.loads(causal_foundation_frontier_fixture_json(fixture))
    assert value["fixture_id"] == fixture.fixture_id
    assert len(value["sources"]) == 5
    assert len(value["records"]) == 16
    assert value["boundary"] == CAUSAL_FOUNDATION_FRONTIER_BOUNDARY


def test_fixture_operation_lookup_accepts_strings(fixture):
    assert len(fixture.operation_records("factor_graph_constructor")) == 4
    assert len(fixture.operation_records("context_conditioned_prior")) == 4
    assert len(fixture.operation_records("measurement_likelihood")) == 4


def test_schema_fields_have_unique_names():
    fields = default_causal_foundation_frontier_fields()
    assert len(fields) == len({item.name for item in fields})
    assert fields[0].name == "record_id"
    assert fields[-1].name == "content_address"


def test_artifact_kind_enum_contains_release_outputs():
    assert CausalFoundationFrontierArtifactKind.REVIEW_CSV.value == "review_csv"
    assert CausalFoundationFrontierArtifactKind.RELEASE.value == "release"
    assert len(tuple(CausalFoundationFrontierArtifactKind)) >= 16
