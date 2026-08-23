"""Depth and assurance checks for the planning frontier."""

from __future__ import annotations

import unittest

from glio_noncode.planning_frontier_assurance import ASSURANCE_DEFINITIONS
from glio_noncode.planning_frontier_fixture_eval import evaluate_planning_fixture
from glio_noncode.planning_frontier_public_data import default_planning_frontier_fixture
from glio_noncode.planning_frontier_runtime import run_planning_runtime


class PlanningDepthTests(unittest.TestCase):
    def test_assurance_definition_count(self) -> None:
        self.assertGreaterEqual(len(ASSURANCE_DEFINITIONS), 60)

    def test_runtime_planes_are_unique(self) -> None:
        report = run_planning_runtime(default_planning_frontier_fixture())
        ids = [item.plane_id for item in report.assurance.planes]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(report.assurance.accepted)

    def test_all_operation_states_are_visible(self) -> None:
        evaluation = evaluate_planning_fixture()
        states = {item.observed_state.value for item in evaluation.executions}
        self.assertTrue({"ready_for_review", "review", "blocked", "abstained"} <= states)


if __name__ == "__main__":
    unittest.main()
