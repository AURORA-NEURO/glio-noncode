from __future__ import annotations

import unittest

from glio_noncode.topology_beta_frontier_acceptance import build_topology_beta_frontier_acceptance
from glio_noncode.topology_beta_frontier_contracts import build_topology_beta_frontier_contracts
from glio_noncode.topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_governance import build_topology_beta_frontier_governance, default_topology_beta_frontier_governance_rules
from glio_noncode.topology_beta_frontier_history import build_topology_beta_frontier_history
from glio_noncode.topology_beta_frontier_integrity import evaluate_topology_beta_frontier_integrity
from glio_noncode.topology_beta_frontier_pipeline import run_topology_beta_frontier_pipeline
from glio_noncode.topology_beta_frontier_public_data import default_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_quality_gate import build_topology_beta_frontier_quality
from glio_noncode.topology_beta_frontier_release_notes import build_topology_beta_frontier_release_notes, render_topology_beta_frontier_release_notes
from glio_noncode.topology_beta_frontier_schema import validate_topology_beta_frontier_schema
from glio_noncode.topology_beta_frontier_reconciliation import reconcile_topology_beta_frontier


class TopologyBetaFrontierGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_beta_frontier_fixture()
        self.evaluation = evaluate_topology_beta_frontier_fixture(self.fixture)

    def test_governance_rules_are_declared_and_pass(self) -> None:
        report = build_topology_beta_frontier_governance(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(default_topology_beta_frontier_governance_rules()), 6)
        self.assertEqual(report.blocking_failures, ())
        self.assertEqual(len(report.decisions_for("loop_stripe")), 4)

    def test_acceptance_gates_join_all_release_inputs(self) -> None:
        pipeline = run_topology_beta_frontier_pipeline(self.fixture)
        report = build_topology_beta_frontier_acceptance(pipeline.evaluation, pipeline.contracts, pipeline.schema, pipeline.quality, pipeline.integrity, pipeline.review_queue)
        self.assertTrue(report.accepted)
        self.assertEqual(report.blocking_failures, ())
        self.assertTrue(report.gate("quality").passed)

    def test_history_has_predecessor_and_latest_release(self) -> None:
        history = build_topology_beta_frontier_history()
        self.assertTrue(history.accepted)
        self.assertEqual(history.latest().status, "accepted")
        self.assertEqual(history.latest().predecessor, history.entries[0].release_id)

    def test_release_notes_are_addressed_and_renderable(self) -> None:
        pipeline = run_topology_beta_frontier_pipeline(self.fixture)
        notes = build_topology_beta_frontier_release_notes(pipeline)
        self.assertTrue(notes.accepted)
        self.assertEqual(len(notes.notes), 6)
        self.assertIn("Aggregate boundary", render_topology_beta_frontier_release_notes(notes))
        self.assertTrue(notes.content_address.startswith("sha256:"))

    def test_acceptance_inputs_remain_individually_green(self) -> None:
        pipeline = run_topology_beta_frontier_pipeline(self.fixture)
        self.assertTrue(validate_topology_beta_frontier_schema(self.fixture, self.evaluation).accepted)
        self.assertTrue(build_topology_beta_frontier_quality(self.fixture, pipeline.data, pipeline.schema, self.evaluation, reconcile_topology_beta_frontier(self.evaluation)).accepted)
        self.assertTrue(evaluate_topology_beta_frontier_integrity(self.fixture, self.evaluation).accepted)


if __name__ == "__main__":
    unittest.main()
