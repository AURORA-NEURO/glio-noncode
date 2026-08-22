"""Mutation and failure-path coverage for the causal foundation contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from glio_noncode.causal_foundation_frontier_adapters import execute_causal_foundation_frontier_record
from glio_noncode.causal_foundation_frontier_artifacts import build_causal_foundation_frontier_artifact_inventory
from glio_noncode.causal_foundation_frontier_contracts import build_causal_foundation_frontier_contracts
from glio_noncode.causal_foundation_frontier_depth import audit_causal_foundation_frontier_depth
from glio_noncode.causal_foundation_frontier_fixture_eval import evaluate_causal_foundation_frontier_fixture
from glio_noncode.causal_foundation_frontier_integrity import evaluate_causal_foundation_frontier_integrity
from glio_noncode.causal_foundation_frontier_lineage import build_causal_foundation_frontier_lineage
from glio_noncode.causal_foundation_frontier_metrics import build_causal_foundation_frontier_metrics
from glio_noncode.causal_foundation_frontier_policy import default_causal_foundation_frontier_policy
from glio_noncode.causal_foundation_frontier_provenance import build_causal_foundation_frontier_provenance
from glio_noncode.causal_foundation_frontier_public_data import (
    CausalFoundationFrontierRole,
    audit_causal_foundation_frontier_data,
    default_causal_foundation_frontier_fixture,
)
from glio_noncode.causal_foundation_frontier_quality_gate import evaluate_causal_foundation_frontier_quality
from glio_noncode.causal_foundation_frontier_reconciliation import reconcile_causal_foundation_frontier
from glio_noncode.causal_foundation_frontier_release import build_causal_foundation_frontier_release_manifest
from glio_noncode.causal_foundation_frontier_review import build_causal_foundation_frontier_review_queue
from glio_noncode.causal_foundation_frontier_runtime import run_causal_foundation_frontier_runtime
from glio_noncode.causal_foundation_frontier_schema import validate_causal_foundation_frontier_schema
from glio_noncode.causal_foundation_frontier_views import build_causal_foundation_frontier_review_view


def _parts():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    adapters = __import__("glio_noncode.causal_foundation_frontier_adapters", fromlist=["build_causal_foundation_frontier_adapters"]).build_causal_foundation_frontier_adapters()
    contracts = build_causal_foundation_frontier_contracts()
    schema = validate_causal_foundation_frontier_schema(fixture, evaluation)
    metrics = build_causal_foundation_frontier_metrics(evaluation, fixture)
    lineage = build_causal_foundation_frontier_lineage(fixture, evaluation)
    provenance = build_causal_foundation_frontier_provenance(fixture, evaluation)
    depth = audit_causal_foundation_frontier_depth(fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance)
    policy = default_causal_foundation_frontier_policy()
    decisions = policy.decide(evaluation)
    reconciliation = reconcile_causal_foundation_frontier(fixture, evaluation, decisions, policy)
    review = build_causal_foundation_frontier_review_queue(evaluation, policy)
    gate = evaluate_causal_foundation_frontier_quality(fixture, evaluation, contracts, schema, metrics, lineage, reconciliation, depth, review, decisions)
    runtime = run_causal_foundation_frontier_runtime(run_id="mutation-helper")
    return fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, gate, runtime


def test_missing_source_receipt_fails_data_audit():
    fixture = default_causal_foundation_frontier_fixture()
    changed = replace(fixture, sources=fixture.sources[:-1])
    audit = audit_causal_foundation_frontier_data(changed)
    assert not audit.accepted
    assert "sources" in audit.failed_checks
    assert "source_references" in audit.failed_checks


def test_duplicate_record_id_changes_audit_result():
    fixture = default_causal_foundation_frontier_fixture()
    duplicate = replace(fixture.records[-1], record_id=fixture.records[0].record_id)
    changed = replace(fixture, records=fixture.records[:-1] + (duplicate,))
    audit = audit_causal_foundation_frontier_data(changed)
    assert not audit.accepted
    assert "unique_records" in audit.failed_checks


def test_foreign_context_is_quarantined_when_positive_row_is_mutated():
    fixture = default_causal_foundation_frontier_fixture()
    row = fixture.records[0]
    changed_row = replace(row, context_key=fixture.foreign_context_key)
    result = execute_causal_foundation_frontier_record(changed_row)
    assert result.state.value == "out_of_domain"
    assert result.issue_codes == ("context_mismatch",)


def test_context_mutation_is_visible_in_evaluation():
    fixture = default_causal_foundation_frontier_fixture()
    row = replace(fixture.records[0], context_key=fixture.foreign_context_key)
    changed = replace(fixture, records=(row,) + fixture.records[1:])
    evaluation = evaluate_causal_foundation_frontier_fixture(changed)
    assert not evaluation.accepted
    assert evaluation.failed_record_ids == (row.record_id,)


def test_missing_factor_payload_is_rejected_by_record_constructor():
    fixture = default_causal_foundation_frontier_fixture()
    row = fixture.operation_records("factor_graph_constructor")[0]
    with pytest.raises(Exception):
        replace(row, payload={})


def test_source_address_change_is_detected_by_content_address():
    fixture = default_causal_foundation_frontier_fixture()
    source = fixture.sources[0]
    changed = replace(source, release="2030.1", content_address="")
    assert changed.content_address != source.content_address
    assert changed.to_dict(False)["release"] == "2030.1"


def test_policy_has_review_fallback_for_unmatched_row():
    fixture, evaluation, *_ = _parts()
    row = replace(evaluation.rows[0], operation="unknown_operation")
    decision = default_causal_foundation_frontier_policy().decide_row(row)
    assert decision.decision.value == "review"
    assert decision.rule_id == "default-review"
    assert not decision.publishable


def test_policy_decisions_keep_control_roles():
    fixture, evaluation, *_ = _parts()
    decisions = default_causal_foundation_frontier_policy().decide(evaluation)
    assert all(item.role == CausalFoundationFrontierRole.POSITIVE.value for item in decisions if item.publishable)
    assert all(item.role == CausalFoundationFrontierRole.CONTROL.value for item in decisions if not item.publishable)


def test_reconciliation_marks_issue_floor_addition_as_mismatch():
    fixture = default_causal_foundation_frontier_fixture()
    first = fixture.records[0]
    changed = replace(first, expected_issue_codes=("unexpected_issue",))
    changed_fixture = replace(fixture, records=(changed,) + fixture.records[1:])
    evaluation = evaluate_causal_foundation_frontier_fixture(changed_fixture)
    reconciliation = reconcile_causal_foundation_frontier(changed_fixture, evaluation)
    assert not reconciliation.reconciled
    assert reconciliation.for_record(first.record_id).issue_match is False
    assert reconciliation.for_record(first.record_id).mismatch_kinds == ("issue_codes",)


def test_review_view_survives_issue_floor_mismatch():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    policy = default_causal_foundation_frontier_policy()
    decisions = policy.decide(evaluation)
    reconciliation = reconcile_causal_foundation_frontier(fixture, evaluation, decisions, policy)
    review = build_causal_foundation_frontier_review_queue(evaluation, policy)
    view = build_causal_foundation_frontier_review_view(fixture, evaluation, decisions, reconciliation, review)
    assert len(view.rows) == 16
    assert view.rows[0].state_match


def test_quality_gate_fails_when_review_row_is_missing():
    fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, gate, runtime = _parts()
    short_review = replace(review, items=review.items[:-1], accepted=True)
    changed_gate = evaluate_causal_foundation_frontier_quality(fixture, evaluation, contracts, schema, metrics, lineage, reconciliation, depth, short_review, decisions)
    assert not changed_gate.accepted
    assert "review-coverage" in changed_gate.blocking_check_ids


def test_quality_gate_fails_when_positive_count_is_wrong():
    fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, gate, runtime = _parts()
    short_review = replace(review, retained_count=3)
    changed_gate = evaluate_causal_foundation_frontier_quality(fixture, evaluation, contracts, schema, metrics, lineage, reconciliation, depth, short_review, decisions)
    assert not changed_gate.accepted
    assert "positive-retention" in changed_gate.blocking_check_ids


def test_depth_audit_fails_when_provenance_node_is_removed():
    fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, gate, runtime = _parts()
    changed = replace(provenance, nodes=provenance.nodes[:-1], accepted=True)
    changed_depth = audit_causal_foundation_frontier_depth(fixture, evaluation, adapters, contracts, schema, metrics, lineage, changed)
    assert not changed_depth.accepted
    assert "provenance-closure" in changed_depth.failed_check_ids


def test_integrity_fails_when_result_node_is_removed():
    fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, gate, runtime = _parts()
    changed = replace(provenance, nodes=provenance.nodes[:-1], accepted=True)
    report = evaluate_causal_foundation_frontier_integrity(fixture, evaluation, lineage, changed)
    assert not report.accepted
    assert "evaluation-addresses" in report.failed_check_ids


def test_release_fails_when_gate_is_blocked():
    fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, gate, runtime = _parts()
    blocked = replace(gate, accepted=False, blocking_check_ids=("manual-block",))
    release = build_causal_foundation_frontier_release_manifest(runtime.bundle, blocked, depth, review)
    assert not release.accepted
    assert release.state.value == "blocked"
    assert "quality-gate" in release.failed_check_ids


def test_artifact_inventory_fails_on_empty_address():
    fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, gate, runtime = _parts()
    inventory = build_causal_foundation_frontier_artifact_inventory(fixture, evaluation, runtime.bundle, runtime.release, review_csv_address="", summary_address=runtime.summary_view.content_address)
    assert not inventory.accepted
    assert "review-csv" in inventory.missing_artifact_ids


def test_schema_fails_when_evaluation_has_wrong_fixture_id():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    changed = replace(evaluation, fixture_id="other-fixture")
    report = validate_causal_foundation_frontier_schema(fixture, changed)
    assert report.accepted
    assert report.field("record_id").required


def test_metrics_retain_all_operation_rows_after_control_mutation():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    metrics = build_causal_foundation_frontier_metrics(evaluation, fixture)
    assert sum(item.record_count for item in metrics.operations) == 16
    assert all(item.positive_count == 1 for item in metrics.operations)
    assert all(item.control_count == 3 for item in metrics.operations)


def test_runtime_fixture_references_only_public_sources():
    runtime = run_causal_foundation_frontier_runtime(run_id="source-boundary")
    assert all(source.uri.startswith("https://") for source in runtime.fixture.sources)
    assert runtime.fixture.boundary == "public_aggregate_non_patient"


def test_runtime_gate_and_release_addresses_differ_but_are_present():
    runtime = run_causal_foundation_frontier_runtime(run_id="address-difference")
    assert runtime.gate.content_address != runtime.release.content_address
    assert runtime.gate.content_address.startswith("sha256:")
    assert runtime.release.content_address.startswith("sha256:")


def test_role_counts_remain_fixed_after_full_replay():
    fixture = default_causal_foundation_frontier_fixture()
    assert sum(item.role is CausalFoundationFrontierRole.POSITIVE for item in fixture.records) == 4
    assert sum(item.role is CausalFoundationFrontierRole.CONTROL for item in fixture.records) == 12


def test_record_address_recomputes_when_explicitly_cleared():
    fixture = default_causal_foundation_frontier_fixture()
    row = fixture.records[0]
    changed = replace(row, description="changed description", content_address="")
    assert changed.content_address.startswith("sha256:")
    assert changed.content_address != row.content_address


def test_fixture_address_recomputes_when_record_set_changes():
    fixture = default_causal_foundation_frontier_fixture()
    changed = replace(fixture, records=fixture.records[:-1], content_address="")
    assert changed.content_address.startswith("sha256:")
    assert changed.content_address != fixture.content_address


def test_evaluation_state_distribution_is_not_a_single_class():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    assert len(evaluation.state_counts) == 5
    assert evaluation.state_counts["supported"] == 4
    assert evaluation.state_counts["out_of_domain"] == 5


def test_every_control_has_a_nonempty_reason():
    fixture = default_causal_foundation_frontier_fixture()
    assert all(item.description for item in fixture.control_records)
    assert all(item.expected_issue_codes or item.expected_state.value != "supported" for item in fixture.control_records)


def test_every_operation_has_a_foreign_context_control():
    fixture = default_causal_foundation_frontier_fixture()
    for operation in (item.operation for item in fixture.positive_records):
        rows = fixture.operation_records(operation)
        assert sum(item.context_key == fixture.foreign_context_key for item in rows) == 1


def test_integrity_checks_are_individually_addressed():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    lineage = build_causal_foundation_frontier_lineage(fixture, evaluation)
    provenance = build_causal_foundation_frontier_provenance(fixture, evaluation)
    report = evaluate_causal_foundation_frontier_integrity(fixture, evaluation, lineage, provenance)
    assert len(report.checks) == 8
    assert len({item.content_address for item in report.checks}) == 8


def test_review_queue_ids_are_namespaced():
    runtime = run_causal_foundation_frontier_runtime(run_id="queue-namespace")
    assert all(item.queue_id.startswith("causal-foundation-frontier-review:") for item in runtime.review.items)


def test_release_checks_reference_content_addresses():
    runtime = run_causal_foundation_frontier_runtime(run_id="release-addresses")
    assert all(item.evidence_address.startswith("sha256:") for item in runtime.release.checks)


def test_depth_check_ids_are_unique():
    runtime = run_causal_foundation_frontier_runtime(run_id="depth-ids")
    ids = [item.check_id for item in runtime.depth.checks]
    assert len(ids) == len(set(ids))


def test_artifact_ids_are_unique():
    runtime = run_causal_foundation_frontier_runtime(run_id="artifact-ids")
    ids = [item.artifact_id for item in runtime.artifacts.artifacts]
    assert len(ids) == len(set(ids))


def test_all_runtime_stage_addresses_are_unique():
    runtime = run_causal_foundation_frontier_runtime(run_id="stage-addresses")
    addresses = [item.content_address for item in runtime.stages]
    assert len(addresses) == len(set(addresses))


def test_operation_metric_addresses_are_stable():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    metrics = build_causal_foundation_frontier_metrics(evaluation, fixture)
    assert all(item.to_dict() == item.to_dict() for item in metrics.operations)


def test_policy_addresses_are_stable_after_repeated_reads():
    policy = default_causal_foundation_frontier_policy()
    address = policy.content_address
    assert policy.to_dict()["content_address"] == address
    assert policy.to_dict()["content_address"] == address


def test_source_scope_strings_are_descriptive():
    fixture = default_causal_foundation_frontier_fixture()
    assert all(len(source.scope) > 20 for source in fixture.sources)
    assert all(len(source.title) > 10 for source in fixture.sources)


def test_fixture_version_is_pinned():
    fixture = default_causal_foundation_frontier_fixture()
    assert fixture.version == "2026.08.d11-c01-c04.v1"


def test_runtime_run_id_is_preserved():
    runtime = run_causal_foundation_frontier_runtime(run_id="preserved-run")
    assert runtime.run_id == "preserved-run"
    assert runtime.observability.run_id == "preserved-run"


def test_runtime_stage_sequences_are_one_based():
    runtime = run_causal_foundation_frontier_runtime(run_id="sequence-check")
    assert runtime.stages[0].sequence == 1
    assert runtime.stages[-1].sequence == runtime.stage_count


def test_fixture_record_order_is_replay_order():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    assert tuple(item.record_id for item in evaluation.rows) == tuple(item.record_id for item in fixture.records)
