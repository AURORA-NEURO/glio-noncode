"""Operational matrix and claim-boundary checks for C01-C04."""

from __future__ import annotations

import json

from glio_noncode.causal_foundation_frontier_assurance import build_causal_foundation_frontier_assurance_summary
from glio_noncode.causal_foundation_frontier_claim_boundary import evaluate_causal_foundation_frontier_claim_boundary
from glio_noncode.causal_foundation_frontier_fixture_eval import evaluate_causal_foundation_frontier_fixture
from glio_noncode.causal_foundation_frontier_operational import build_causal_foundation_frontier_operational_matrix
from glio_noncode.causal_foundation_frontier_public_data import default_causal_foundation_frontier_fixture
from glio_noncode.causal_foundation_frontier_runtime import run_causal_foundation_frontier_runtime


def test_operational_matrix_has_every_record():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    matrix = build_causal_foundation_frontier_operational_matrix(fixture, evaluation)
    assert matrix.accepted
    assert len(matrix.cells) == 16
    assert matrix.retain_count == 4
    assert matrix.review_count == 4
    assert matrix.blocked_count == 8
    assert len(matrix.for_state("supported")) == 4
    assert len(matrix.for_effect("retained")) == 4
    assert len(matrix.for_effect("blocked")) == 8
    assert all(item.content_address.startswith("sha256:") for item in matrix.cells)


def test_operational_matrix_has_four_cells_per_operation():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    matrix = build_causal_foundation_frontier_operational_matrix(fixture, evaluation)
    for operation in ("typed_hypothesis_object", "factor_graph_constructor", "context_conditioned_prior", "measurement_likelihood"):
        assert len(matrix.for_operation(operation)) == 4


def test_operational_actions_are_specific():
    fixture = default_causal_foundation_frontier_fixture()
    evaluation = evaluate_causal_foundation_frontier_fixture(fixture)
    matrix = build_causal_foundation_frontier_operational_matrix(fixture, evaluation)
    retained = matrix.for_effect("retained")
    blocked = matrix.for_effect("blocked")
    review = matrix.for_effect("review")
    assert all("receipt" in item.action for item in retained)
    assert all("prevent release" in item.action for item in blocked)
    assert all("review" in item.action or "evidence" in item.action or "coverage" in item.action for item in review)


def test_claim_boundary_accepts_runtime_release():
    runtime = run_causal_foundation_frontier_runtime(run_id="boundary-test")
    report = evaluate_causal_foundation_frontier_claim_boundary(runtime.bundle, runtime.release)
    assert report.accepted
    assert report.failed_check_ids == ()
    assert len(report.checks) == 7
    assert all(item.content_address.startswith("sha256:") for item in report.checks)


def test_claim_boundary_mentions_all_excluded_uses():
    runtime = run_causal_foundation_frontier_runtime(run_id="boundary-test-2")
    report = evaluate_causal_foundation_frontier_claim_boundary(runtime.bundle, runtime.release)
    phrases = {item.phrase for item in report.checks}
    assert "patient care" in phrases
    assert "diagnostic determination" in phrases
    assert "treatment selection" in phrases


def test_assurance_summary_is_handoff_ready():
    runtime = run_causal_foundation_frontier_runtime(run_id="assurance-test")
    boundary = evaluate_causal_foundation_frontier_claim_boundary(runtime.bundle, runtime.release)
    summary = build_causal_foundation_frontier_assurance_summary(runtime, boundary)
    assert summary.accepted
    assert summary.stage_count == 19
    assert summary.record_count == 16
    assert summary.positive_count == 4
    assert summary.control_count == 12
    assert summary.passed_quality_checks == 13
    assert summary.failed_quality_checks == 0
    assert summary.depth_passed == summary.depth_required == 10
    assert summary.release_state == "ready"
    assert summary.claim_boundary_accepted
    assert summary.retained_count == 4
    assert summary.blocked_count == 10
    assert len(summary.key_limitations) == 3
    assert summary.content_address.startswith("sha256:")


def test_assurance_summary_json_is_stable():
    runtime = run_causal_foundation_frontier_runtime(run_id="assurance-json")
    boundary = evaluate_causal_foundation_frontier_claim_boundary(runtime.bundle, runtime.release)
    summary = build_causal_foundation_frontier_assurance_summary(runtime, boundary)
    value = json.loads(json.dumps(summary.to_dict(), default=str))
    assert value["run_id"] == "assurance-json"
    assert value["accepted"] is True
    assert value["content_address"].startswith("sha256:")


def test_empty_boundary_is_not_accepted():
    runtime = run_causal_foundation_frontier_runtime(run_id="empty-boundary")
    report = evaluate_causal_foundation_frontier_claim_boundary(runtime.bundle, runtime.release)
    empty = type(report)((), False)
    summary = build_causal_foundation_frontier_assurance_summary(runtime, empty)
    assert not summary.claim_boundary_accepted
    assert summary.accepted
