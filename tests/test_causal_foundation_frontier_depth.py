"""Depth, release, and mutation tests for the C01-C04 pipeline."""

from __future__ import annotations

from dataclasses import replace

import pytest

from glio_noncode.causal_foundation_frontier_adapters import build_causal_foundation_frontier_adapters
from glio_noncode.causal_foundation_frontier_artifacts import (
    CausalFoundationFrontierArtifactKind,
    build_causal_foundation_frontier_artifact_inventory,
)
from glio_noncode.causal_foundation_frontier_bundle import (
    CausalFoundationFrontierBundleState,
)
from glio_noncode.causal_foundation_frontier_contracts import build_causal_foundation_frontier_contracts
from glio_noncode.causal_foundation_frontier_depth import audit_causal_foundation_frontier_depth
from glio_noncode.causal_foundation_frontier_fixture_eval import evaluate_causal_foundation_frontier_fixture
from glio_noncode.causal_foundation_frontier_integrity import evaluate_causal_foundation_frontier_integrity
from glio_noncode.causal_foundation_frontier_lineage import build_causal_foundation_frontier_lineage
from glio_noncode.causal_foundation_frontier_metrics import build_causal_foundation_frontier_metrics
from glio_noncode.causal_foundation_frontier_observability import (
    build_causal_foundation_frontier_observability,
    record_causal_foundation_frontier_event,
)
from glio_noncode.causal_foundation_frontier_policy import default_causal_foundation_frontier_policy
from glio_noncode.causal_foundation_frontier_provenance import build_causal_foundation_frontier_provenance
from glio_noncode.causal_foundation_frontier_quality_gate import evaluate_causal_foundation_frontier_quality
from glio_noncode.causal_foundation_frontier_public_data import default_causal_foundation_frontier_fixture
from glio_noncode.causal_foundation_frontier_reconciliation import reconcile_causal_foundation_frontier
from glio_noncode.causal_foundation_frontier_release import build_causal_foundation_frontier_release_manifest
from glio_noncode.causal_foundation_frontier_replay import compare_causal_foundation_frontier_replays
from glio_noncode.causal_foundation_frontier_review import build_causal_foundation_frontier_review_queue
from glio_noncode.causal_foundation_frontier_runtime import run_causal_foundation_frontier_runtime
from glio_noncode.causal_foundation_frontier_scenario_matrix import build_causal_foundation_frontier_scenario_matrix
from glio_noncode.causal_foundation_frontier_schema import validate_causal_foundation_frontier_schema
from glio_noncode.causal_foundation_frontier_validation_matrix import build_causal_foundation_frontier_validation_matrix
from glio_noncode.causal_foundation_frontier_views import (
    build_causal_foundation_frontier_review_view,
    build_causal_foundation_frontier_summary_view,
)


@pytest.fixture(scope="module")
def runtime():
    return run_causal_foundation_frontier_runtime(run_id="depth-test")


def test_runtime_has_ordered_stages(runtime):
    assert runtime.accepted
    assert runtime.stage_count == 19
    assert runtime.stage_ids == (
        "data-audit",
        "adapters",
        "contracts",
        "fixture-replay",
        "schema",
        "metrics",
        "lineage",
        "provenance",
        "depth-audit",
        "policy",
        "decisions",
        "reconciliation",
        "review-queue",
        "review-view",
        "summary-view",
        "quality-gate",
        "release-bundle",
        "release-manifest",
        "artifact-inventory",
    )
    assert [item.sequence for item in runtime.stages] == list(range(1, 20))
    assert all(item.state == "completed" for item in runtime.stages)


def test_runtime_outputs_are_cross_linked(runtime):
    assert runtime.bundle.fixture_address == runtime.fixture.content_address
    assert runtime.bundle.evaluation_address == runtime.evaluation.content_address
    assert runtime.bundle.metrics_address == runtime.metrics.content_address
    assert runtime.bundle.contracts_address == runtime.contracts.content_address
    assert runtime.bundle.schema_address == runtime.schema.content_address
    assert runtime.bundle.lineage_address == runtime.lineage.content_address
    assert runtime.bundle.provenance_address == runtime.provenance.content_address
    assert runtime.bundle.depth_address == runtime.depth.content_address
    assert runtime.bundle.reconciliation_address == runtime.reconciliation.content_address
    assert runtime.bundle.policy_address == runtime.policy.content_address
    assert runtime.bundle.review_address == runtime.review.content_address
    assert runtime.bundle.quality_gate_address == runtime.gate.content_address


def test_depth_audit_has_ten_passed_checks(runtime):
    assert runtime.depth.accepted
    assert runtime.depth.passed_count == 10
    assert runtime.depth.required_count == 10
    assert runtime.depth.failed_check_ids == ()
    assert all(item.content_address.startswith("sha256:") for item in runtime.depth.checks)


def test_quality_gate_has_explicit_checks(runtime):
    assert runtime.gate.accepted
    assert runtime.gate.blocking_check_ids == ()
    assert runtime.gate.passed_count == 13
    assert runtime.gate.failed_count == 0
    assert runtime.gate.review_check_ids == ()
    assert runtime.gate.check("no-patient-boundary").passed


def test_release_manifest_is_ready(runtime):
    assert runtime.release.accepted
    assert runtime.release.state.value == "ready"
    assert runtime.release.passed_count == 5
    assert runtime.release.failed_check_ids == ()
    assert "patient care" in runtime.release.excluded_uses
    assert "aggregate evidence review" in runtime.release.allowed_uses


def test_bundle_is_ready_and_bounded(runtime):
    assert runtime.bundle.state is CausalFoundationFrontierBundleState.READY
    assert runtime.bundle.publishable
    assert "individual risk scoring" in runtime.bundle.excluded_uses
    assert len(runtime.bundle.allowed_uses) == 4
    assert all(address.startswith("sha256:") for address in runtime.bundle.to_dict(False).values() if isinstance(address, str) and "address" in str(address))


def test_artifact_inventory_is_complete(runtime):
    inventory = runtime.artifacts
    assert inventory.accepted
    assert inventory.required_count == 16
    assert inventory.resolved_count == 16
    assert inventory.missing_artifact_ids == ()
    assert len(inventory.for_kind(CausalFoundationFrontierArtifactKind.REVIEW_CSV)) == 1
    assert len(inventory.for_kind("release")) == 1
    assert all(item.relative_path for item in inventory.artifacts)


def test_observability_matches_runtime(runtime):
    report = runtime.observability
    assert report.accepted
    assert report.completed_count == 19
    assert report.failed_count == 0
    assert report.stage_ids == runtime.stage_ids
    assert report.total_duration_ms >= 0.0


def test_observability_records_success_and_failure():
    value, success = record_causal_foundation_frontier_event("obs", 1, "ok", lambda: {"value": 1}, "success")
    failed_value, failure = record_causal_foundation_frontier_event("obs", 2, "bad", lambda: 1 / 0, "failure")
    report = build_causal_foundation_frontier_observability("obs", (success, failure))
    assert value == {"value": 1}
    assert failed_value is None
    assert success.state == "completed"
    assert failure.state == "failed"
    assert not report.accepted
    assert report.completed_count == 1
    assert report.failed_count == 1


def test_release_rebuild_is_addressable(runtime):
    release = build_causal_foundation_frontier_release_manifest(runtime.bundle, runtime.gate, runtime.depth, runtime.review, release_id="rebuild")
    assert release.accepted
    assert release.release_id == "rebuild"
    assert release.content_address.startswith("sha256:")
    assert release.bundle_address == runtime.bundle.content_address


def test_artifact_inventory_rebuild_is_deterministic(runtime):
    left = build_causal_foundation_frontier_artifact_inventory(runtime.fixture, runtime.evaluation, runtime.bundle, runtime.release, review_csv_address=runtime.review_view.content_address, summary_address=runtime.summary_view.content_address)
    right = build_causal_foundation_frontier_artifact_inventory(runtime.fixture, runtime.evaluation, runtime.bundle, runtime.release, review_csv_address=runtime.review_view.content_address, summary_address=runtime.summary_view.content_address)
    assert left.content_address == right.content_address
    assert [item.to_dict() for item in left.artifacts] == [item.to_dict() for item in right.artifacts]


def test_validation_and_scenario_matrices_share_fixture(runtime):
    scenarios = build_causal_foundation_frontier_scenario_matrix(runtime.fixture, runtime.evaluation)
    matrix = build_causal_foundation_frontier_validation_matrix(runtime.fixture, runtime.evaluation)
    assert scenarios.fixture_id == matrix.fixture_id == runtime.fixture.fixture_id
    assert scenarios.accepted and matrix.accepted
    assert len(matrix.for_scenario("positive")) == 4
    assert len(matrix.for_scenario("contradictory")) == 3
    assert len(matrix.for_scenario("missing_or_partial")) == 5
    assert len(matrix.for_scenario("foreign_context")) == 4


def test_runtime_summary_is_consistent(runtime):
    summary = runtime.summary_view
    assert summary.fixture_id == runtime.fixture.fixture_id
    assert summary.metrics.content_address == runtime.metrics.content_address
    assert summary.retained_count == runtime.review.retained_count
    assert summary.review_count == runtime.review.review_count
    assert summary.quarantine_count == runtime.review.blocked_count
    assert summary.accepted is True


def test_runtime_review_view_has_one_row_per_record(runtime):
    assert len(runtime.review_view.rows) == len(runtime.fixture.records)
    assert set(item.record_id for item in runtime.review_view.rows) == set(item.record_id for item in runtime.fixture.records)
    assert len(runtime.review_view.columns) == 12
    assert runtime.review_view.to_csv().endswith("\n")


def test_integrity_report_reuses_runtime_graphs(runtime):
    report = evaluate_causal_foundation_frontier_integrity(runtime.fixture, runtime.evaluation, runtime.lineage, runtime.provenance)
    assert report.accepted
    assert report.failed_check_ids == ()
    assert all(item.content_address.startswith("sha256:") for item in report.checks)


def test_replay_comparison_is_identical(runtime):
    comparison = compare_causal_foundation_frontier_replays(runtime.evaluation, runtime.evaluation)
    assert comparison.accepted
    assert comparison.identical
    assert comparison.changed_record_ids == ()


def test_runtime_serialization_contains_all_planes(runtime):
    value = runtime.to_dict()
    for key in (
        "fixture",
        "evaluation",
        "metrics",
        "contracts",
        "schema",
        "lineage",
        "provenance",
        "depth",
        "policy",
        "decisions",
        "reconciliation",
        "review",
        "review_view",
        "summary_view",
        "gate",
        "bundle",
        "release",
        "artifacts",
        "stages",
        "observability",
    ):
        assert key in value
    assert value["stage_count"] == 19
    assert value["accepted"] is True


def test_public_fixture_is_not_patient_level(runtime):
    assert runtime.fixture.boundary == "public_aggregate_non_patient"
    assert all("patient" not in source.scope.lower() for source in runtime.fixture.sources)
    assert all("subject" not in record.description.lower() for record in runtime.fixture.records)


def test_runtime_addresses_are_nonempty(runtime):
    assert runtime.content_address.startswith("sha256:")
    assert runtime.observability.content_address.startswith("sha256:")
    assert all(item.output_address for item in runtime.stages)
    assert all(item.content_address.startswith("sha256:") for item in runtime.stages)


def test_runtime_can_be_repeated_with_same_fixture(runtime):
    second = run_causal_foundation_frontier_runtime(runtime.fixture, run_id="depth-test")
    assert second.accepted
    assert second.evaluation.content_address == runtime.evaluation.content_address
    assert second.metrics.content_address == runtime.metrics.content_address
    assert second.bundle.content_address == runtime.bundle.content_address
    assert second.release.content_address == runtime.release.content_address


def test_missing_fixture_row_is_detectable():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    reduced = replace(fixture, records=fixture.records[:-1])
    reduced_evaluation = evaluate_causal_foundation_frontier_fixture(reduced)
    assert reduced_evaluation.accepted
    assert len(reduced_evaluation.rows) == 15
    assert reduced_evaluation.content_address != evaluation.content_address


def test_mutated_expected_state_fails_evaluation():
    fixture = default_causal_foundation_frontier_fixture()
    first = fixture.records[0]
    mutated = replace(first, expected_state=next(item for item in type(first.expected_state) if item.value == "partial"))
    changed = replace(fixture, records=(mutated,) + fixture.records[1:])
    evaluation = evaluate_causal_foundation_frontier_fixture(changed)
    assert not evaluation.accepted
    assert evaluation.failed_record_ids == (first.record_id,)
    assert evaluation.state_match_count == 15


def test_mutated_expected_issue_floor_fails_reconciliation():
    fixture = default_causal_foundation_frontier_fixture()
    first = fixture.records[0]
    mutated = replace(first, expected_issue_codes=("unexpected_control",))
    changed = replace(fixture, records=(mutated,) + fixture.records[1:])
    evaluation = evaluate_causal_foundation_frontier_fixture(changed)
    policy = default_causal_foundation_frontier_policy()
    reconciliation = reconcile_causal_foundation_frontier(changed, evaluation, policy=policy)
    assert not reconciliation.reconciled
    assert reconciliation.mismatch_record_ids == (first.record_id,)


def test_schema_detects_record_count_mismatch_when_evaluation_is_shorter():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    short = replace(evaluation, rows=evaluation.rows[:-1])
    report = validate_causal_foundation_frontier_schema(fixture, short)
    assert not report.accepted
    assert "evaluation_rows" in report.failed_checks


def test_depth_audit_surfaces_missing_result_edge(runtime):
    removed = runtime.lineage.record_edges[-1]
    lineage = replace(runtime.lineage, edges=tuple(item for item in runtime.lineage.edges if item is not removed), accepted=True)
    depth = audit_causal_foundation_frontier_depth(runtime.fixture, runtime.evaluation, runtime.adapters if hasattr(runtime, "adapters") else build_causal_foundation_frontier_adapters(), runtime.contracts, runtime.schema, runtime.metrics, lineage, runtime.provenance)
    assert not depth.accepted
    assert "lineage-closure" in depth.failed_check_ids


def test_quality_gate_is_blocking_when_evaluation_changes(runtime):
    changed = replace(runtime.evaluation, accepted=False)
    reconciliation = reconcile_causal_foundation_frontier(runtime.fixture, changed, runtime.decisions, runtime.policy)
    gate = evaluate_causal_foundation_frontier_quality(runtime.fixture, changed, runtime.contracts, runtime.schema, runtime.metrics, runtime.lineage, reconciliation, runtime.depth, runtime.review, runtime.decisions)
    assert not gate.accepted
    assert "evaluation" in gate.blocking_check_ids


def test_content_addresses_are_stable_across_to_dict_calls(runtime):
    objects = (runtime.fixture, runtime.evaluation, runtime.metrics, runtime.lineage, runtime.provenance, runtime.depth, runtime.review, runtime.gate, runtime.bundle, runtime.release, runtime.artifacts)
    for item in objects:
        before = item.content_address
        item.to_dict()
        assert item.content_address == before
