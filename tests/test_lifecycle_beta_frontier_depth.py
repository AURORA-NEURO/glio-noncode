from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.lifecycle_beta_frontier_assurance import build_lifecycle_beta_frontier_assurance_summary
from glio_noncode.lifecycle_beta_frontier_change_control import default_lifecycle_beta_frontier_change_control
from glio_noncode.lifecycle_beta_frontier_claim_boundary import evaluate_lifecycle_beta_frontier_claim_boundary
from glio_noncode.lifecycle_beta_frontier_compatibility import evaluate_lifecycle_beta_frontier_compatibility
from glio_noncode.lifecycle_beta_frontier_compliance import evaluate_lifecycle_beta_frontier_compliance
from glio_noncode.lifecycle_beta_frontier_controls import build_lifecycle_beta_frontier_control_coverage
from glio_noncode.lifecycle_beta_frontier_data_dictionary import default_lifecycle_beta_frontier_data_dictionary
from glio_noncode.lifecycle_beta_frontier_depth import audit_lifecycle_beta_frontier_depth
from glio_noncode.lifecycle_beta_frontier_diagnostics import diagnose_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_failure_injection import run_lifecycle_beta_frontier_failure_injections
from glio_noncode.lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_handoff import (
    build_lifecycle_beta_frontier_handoff,
    lifecycle_beta_frontier_handoff_summary,
    render_lifecycle_beta_frontier_handoff_markdown,
    validate_lifecycle_beta_frontier_handoff,
)
from glio_noncode.lifecycle_beta_frontier_integrity import evaluate_lifecycle_beta_frontier_integrity
from glio_noncode.lifecycle_beta_frontier_metrics import measure_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_operational import build_lifecycle_beta_frontier_operational_matrix
from glio_noncode.lifecycle_beta_frontier_performance import build_lifecycle_beta_frontier_performance_budget
from glio_noncode.lifecycle_beta_frontier_policy import default_lifecycle_beta_frontier_policy
from glio_noncode.lifecycle_beta_frontier_projection_assertions import assert_lifecycle_beta_frontier_projection
from glio_noncode.lifecycle_beta_frontier_public_data import audit_lifecycle_beta_frontier_data, default_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_quality_gate import run_lifecycle_beta_frontier_quality_gate
from glio_noncode.lifecycle_beta_frontier_reconciliation import reconcile_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_release import build_lifecycle_beta_frontier_release
from glio_noncode.lifecycle_beta_frontier_replay import replay_lifecycle_beta_frontier_evaluation
from glio_noncode.lifecycle_beta_frontier_recovery import build_lifecycle_beta_frontier_recovery_plan
from glio_noncode.lifecycle_beta_frontier_review_queue import build_lifecycle_beta_frontier_review_queue
from glio_noncode.lifecycle_beta_frontier_review_sla import build_lifecycle_beta_frontier_review_sla
from glio_noncode.lifecycle_beta_frontier_runbook import build_lifecycle_beta_frontier_runbook
from glio_noncode.lifecycle_beta_frontier_runtime import run_lifecycle_beta_frontier_runtime
from glio_noncode.lifecycle_beta_frontier_scenario_matrix import evaluate_lifecycle_beta_frontier_scenarios, validate_lifecycle_beta_frontier_scenarios
from glio_noncode.lifecycle_beta_frontier_schema import default_lifecycle_beta_frontier_schema
from glio_noncode.lifecycle_beta_frontier_support import default_lifecycle_beta_frontier_support_directory
from glio_noncode.lifecycle_beta_frontier_thresholds import build_lifecycle_beta_frontier_threshold_report, validate_lifecycle_beta_frontier_threshold_report
from glio_noncode.lifecycle_beta_frontier_validation_matrix import build_lifecycle_beta_frontier_validation_matrix, validate_lifecycle_beta_frontier_matrix


class LifecycleBetaFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_lifecycle_beta_frontier_fixture()
        self.audit = audit_lifecycle_beta_frontier_data(self.fixture)
        self.evaluation = evaluate_lifecycle_beta_frontier_fixture(self.fixture)
        self.metrics = measure_lifecycle_beta_frontier(self.evaluation)
        self.policy = default_lifecycle_beta_frontier_policy()
        self.runtime = run_lifecycle_beta_frontier_runtime(self.fixture, run_id="depth-test")
        self.handoff = build_lifecycle_beta_frontier_handoff(self.fixture, self.evaluation, self.metrics)

    def test_runtime_has_twenty_five_stages(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 25)
        self.assertEqual(tuple(item.sequence for item in self.runtime.stages), tuple(range(1, 26)))
        self.assertEqual(self.runtime.stage_ids[0], "data-audit")
        self.assertEqual(self.runtime.stage_ids[-1], "handoff-summary")

    def test_thresholds_have_five_probes_per_operation(self) -> None:
        thresholds = self.runtime.thresholds
        self.assertTrue(validate_lifecycle_beta_frontier_threshold_report(thresholds))
        self.assertEqual(thresholds.profile_count, 8)
        self.assertEqual(thresholds.probe_count, 40)
        for profile in thresholds.profiles:
            self.assertEqual(len(thresholds.by_operation(profile.operation)), 5)

    def test_validation_matrix_has_six_planes(self) -> None:
        matrix = self.runtime.validation_matrix
        self.assertTrue(validate_lifecycle_beta_frontier_matrix(matrix))
        self.assertEqual(matrix.cell_count, 32)
        self.assertEqual(matrix.operation_count, 8)
        for plane in matrix.axes:
            self.assertEqual(len(matrix.by_plane(plane)), 32)

    def test_scenario_matrix_has_four_axes_per_operation(self) -> None:
        matrix = evaluate_lifecycle_beta_frontier_scenarios(self.evaluation)
        self.assertTrue(validate_lifecycle_beta_frontier_scenarios(matrix))
        self.assertEqual(len(matrix.cells), 32)
        self.assertEqual(len(matrix.axes), 4)

    def test_depth_audit_is_green(self) -> None:
        audit = audit_lifecycle_beta_frontier_depth(self.fixture, self.evaluation, self.runtime.validation_matrix, self.handoff)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertEqual(len(audit.checks), 9)

    def test_claim_boundary_is_closed(self) -> None:
        report = evaluate_lifecycle_beta_frontier_claim_boundary(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 32)

    def test_integrity_is_closed(self) -> None:
        report = evaluate_lifecycle_beta_frontier_integrity(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 6)

    def test_compliance_is_closed(self) -> None:
        report = evaluate_lifecycle_beta_frontier_compliance(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 5)

    def test_assurance_is_closed(self) -> None:
        assurance = build_lifecycle_beta_frontier_assurance_summary(
            self.fixture,
            self.evaluation,
            self.runtime.quality,
            self.runtime.stages[13] and replay_lifecycle_beta_frontier_evaluation(self.fixture, self.evaluation),
            self.policy,
        )
        self.assertTrue(assurance.accepted)
        self.assertEqual(assurance.controls_total, 24)

    def test_failure_injections_are_contained(self) -> None:
        report = run_lifecycle_beta_frontier_failure_injections(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.injections), 8)
        self.assertTrue(all(item.contained for item in report.injections))

    def test_control_coverage_is_complete(self) -> None:
        report = build_lifecycle_beta_frontier_control_coverage(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.rows), 8)
        self.assertTrue(all(item.control_count == 3 for item in report.rows))

    def test_operational_matrix_has_blocking_controls(self) -> None:
        matrix = build_lifecycle_beta_frontier_operational_matrix(self.evaluation)
        self.assertEqual(len(matrix.rows), 32)
        self.assertGreater(matrix.blocking_count, 0)

    def test_review_sla_and_recovery_are_addressed(self) -> None:
        queue = build_lifecycle_beta_frontier_review_queue(self.evaluation)
        sla = build_lifecycle_beta_frontier_review_sla(queue)
        recovery = build_lifecycle_beta_frontier_recovery_plan(self.runtime)
        self.assertEqual(len(sla.rows), 32)
        self.assertEqual(sla.unassigned_count, 0)
        self.assertEqual(len(recovery.actions), 25)
        self.assertTrue(recovery.safe_to_resume)

    def test_runbook_has_stop_conditions(self) -> None:
        runbook = build_lifecycle_beta_frontier_runbook(self.runtime)
        self.assertEqual(len(runbook.steps), 5)
        self.assertTrue(all(item.stop_if for item in runbook.steps))

    def test_diagnostics_and_performance_are_addressed(self) -> None:
        diagnostics = diagnose_lifecycle_beta_frontier(self.runtime)
        performance = build_lifecycle_beta_frontier_performance_budget(self.runtime)
        self.assertTrue(diagnostics.accepted)
        self.assertTrue(performance.accepted)
        self.assertEqual(performance.stage_count, 25)

    def test_data_dictionary_and_support_directory_are_complete(self) -> None:
        dictionary = default_lifecycle_beta_frontier_data_dictionary()
        support = default_lifecycle_beta_frontier_support_directory()
        change = default_lifecycle_beta_frontier_change_control()
        self.assertEqual(len(dictionary.entries), 8)
        self.assertEqual(len(support.routes), 6)
        self.assertTrue(change.accepted)
        self.assertFalse(change.migration_required)

    def test_compatibility_and_projection_are_green(self) -> None:
        compatibility = evaluate_lifecycle_beta_frontier_compatibility(self.fixture, default_lifecycle_beta_frontier_schema())
        projection = assert_lifecycle_beta_frontier_projection(self.evaluation)
        self.assertTrue(compatibility.accepted)
        self.assertTrue(projection.accepted)

    def test_handoff_markdown_and_summary_are_reviewable(self) -> None:
        markdown = render_lifecycle_beta_frontier_handoff_markdown(self.handoff)
        summary = lifecycle_beta_frontier_handoff_summary(self.handoff)
        self.assertTrue(validate_lifecycle_beta_frontier_handoff(self.handoff))
        self.assertIn("# Lifecycle-beta frontier research handoff", markdown)
        self.assertIn("## Reproducibility", markdown)
        self.assertEqual(summary["record_count"], 32)

    def test_runtime_json_projection_has_depth_counts(self) -> None:
        payload = self.runtime.to_dict()
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["thresholds"]["probe_count"], 40)
        self.assertEqual(payload["validation_matrix"]["cell_count"], 32)
        self.assertEqual(payload["handoff"]["operation_count"], 8)


if __name__ == "__main__":
    unittest.main()
