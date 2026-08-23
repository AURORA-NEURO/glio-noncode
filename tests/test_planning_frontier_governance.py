"""Governance, views, handoff, and release-manifest tests."""

from __future__ import annotations

import unittest

from glio_noncode.planning_frontier_contracts import PlanningOperation
from glio_noncode.planning_frontier_fixture_eval import evaluate_planning_fixture
from glio_noncode.planning_frontier_governance import (
    build_planning_artifact_inventory,
    build_planning_claim_boundary,
    build_planning_control_coverage,
    build_planning_operational_matrix,
    build_planning_scenario_matrix,
)
from glio_noncode.planning_frontier_handoff import build_planning_handoff
from glio_noncode.planning_frontier_public_data import default_planning_frontier_fixture
from glio_noncode.planning_frontier_run_manifest import build_planning_run_manifest
from glio_noncode.planning_frontier_thresholds import build_planning_threshold_report
from glio_noncode.planning_frontier_validation_matrix import build_planning_validation_matrix
from glio_noncode.planning_frontier_views import build_planning_review_view, build_planning_summary_view


class PlanningGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_planning_frontier_fixture()
        self.evaluation = evaluate_planning_fixture(self.fixture)

    def test_control_coverage_is_balanced(self) -> None:
        coverage = build_planning_control_coverage(self.evaluation)
        self.assertTrue(coverage.accepted)
        self.assertEqual(coverage.role_counts, {"positive": 4, "control": 12})
        self.assertEqual(sorted(coverage.operation_counts.values()), [4, 4, 4, 4])

    def test_scenario_and_operational_matrices_close(self) -> None:
        scenarios = build_planning_scenario_matrix(self.fixture, self.evaluation)
        operational = build_planning_operational_matrix(self.evaluation)
        self.assertTrue(scenarios.accepted)
        self.assertTrue(operational.accepted)
        self.assertEqual(len(scenarios.rows), 16)
        self.assertEqual(len(operational.rows), 16)

    def test_artifact_inventory_is_addressed(self) -> None:
        inventory = build_planning_artifact_inventory(self.fixture, self.evaluation)
        self.assertTrue(inventory.accepted)
        self.assertGreater(len(inventory.artifacts), 90)

    def test_claim_boundary_is_explicit(self) -> None:
        boundary = build_planning_claim_boundary()
        self.assertTrue(boundary.accepted)
        self.assertIn("individual-level inference", boundary.excluded_uses)

    def test_views_keep_four_operations_and_held_states(self) -> None:
        review = build_planning_review_view(self.evaluation)
        summary = build_planning_summary_view(self.fixture, self.evaluation)
        self.assertTrue(review.accepted)
        self.assertTrue(summary.operation_summaries)
        self.assertEqual(len(summary.operation_summaries), 4)
        self.assertEqual(review.counts["blocked"], 4)

    def test_handoff_and_manifest_are_reviewable(self) -> None:
        handoff = build_planning_handoff(self.fixture, self.evaluation)
        manifest = build_planning_run_manifest(self.fixture)
        self.assertTrue(handoff.accepted)
        self.assertEqual(handoff.summary["held_count"], 12)
        self.assertEqual(set(manifest.operation_names), {item.value for item in PlanningOperation})
        self.assertTrue(manifest.content_address.startswith("planning-run-manifest:"))

    def test_thresholds_and_validation_matrix_close(self) -> None:
        thresholds = build_planning_threshold_report()
        matrix = build_planning_validation_matrix(self.fixture, self.evaluation)
        self.assertTrue(thresholds.accepted)
        self.assertTrue(matrix.accepted)
        self.assertEqual(matrix.plane_counts["state"], 16)


if __name__ == "__main__":
    unittest.main()
