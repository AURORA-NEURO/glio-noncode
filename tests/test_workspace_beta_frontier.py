from __future__ import annotations

import unittest

from glio_noncode.workspace_beta_frontier_accessibility import evaluate_beta_frontier_accessibility
from glio_noncode.workspace_beta_frontier_artifacts import (
    BetaFrontierArtifactKind,
    build_beta_frontier_artifact_inventory,
)
from glio_noncode.workspace_beta_frontier_checks import run_beta_frontier_invariants
from glio_noncode.workspace_beta_frontier_compliance import evaluate_beta_frontier_boundary
from glio_noncode.workspace_beta_frontier_depth import audit_beta_frontier_depth
from glio_noncode.workspace_beta_frontier_fixture_eval import evaluate_beta_frontier_fixture
from glio_noncode.workspace_beta_frontier_metrics import measure_beta_frontier
from glio_noncode.workspace_beta_frontier_observability import observe_beta_frontier
from glio_noncode.workspace_beta_frontier_policy import default_beta_frontier_policy
from glio_noncode.workspace_beta_frontier_projection_assertions import (
    audit_beta_frontier_projections,
)
from glio_noncode.workspace_beta_frontier_public_data import (
    BETA_FRONTIER_CONTEXT_KEY,
    BetaFrontierOperation,
    audit_beta_frontier_data,
    build_beta_frontier_catalog,
    default_beta_frontier_fixture,
)
from glio_noncode.workspace_beta_frontier_release import build_beta_frontier_release_manifest
from glio_noncode.workspace_beta_frontier_replay import (
    beta_frontier_replay_is_deterministic,
    replay_beta_frontier,
)
from glio_noncode.workspace_beta_frontier_review_queue import build_beta_frontier_review_queue
from glio_noncode.workspace_beta_frontier_runbook import default_beta_frontier_runbook
from glio_noncode.workspace_beta_frontier_runtime import run_beta_frontier_runtime
from glio_noncode.workspace_beta_frontier_scenario_matrix import build_beta_frontier_scenario_matrix
from glio_noncode.workspace_beta_frontier_schema import default_beta_frontier_schema
from glio_noncode.workspace_beta_frontier_thresholds import build_beta_frontier_threshold_report
from glio_noncode.workspace_beta_frontier_validation_matrix import (
    BetaFrontierValidationStatus,
    build_beta_frontier_validation_matrix,
)
from glio_noncode.workspace_beta_frontier_views import build_beta_frontier_review_view


class WorkspaceBetaFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_beta_frontier_fixture()
        self.evaluation = evaluate_beta_frontier_fixture(self.fixture)

    def test_public_fixture_is_balanced_and_addressed(self) -> None:
        self.assertEqual(self.fixture.context_key, BETA_FRONTIER_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(audit_beta_frontier_data(self.fixture).accepted)
        self.assertTrue(build_beta_frontier_catalog(self.fixture).content_address.startswith("sha256:"))

    def test_each_projection_surface_has_positive_and_controls(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        for operation in BetaFrontierOperation:
            rows = self.evaluation.by_operation(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role.value == "positive" for item in rows), 1)
            self.assertEqual(sum(item.role.value == "control" for item in rows), 3)

    def test_topology_and_causal_states_remain_visible(self) -> None:
        topology = self.evaluation.execution_map()["topology-positive"]
        self.assertEqual(topology.state, "supported")
        self.assertGreaterEqual(topology.output["edge_count"], 2)
        self.assertIn("context_mismatch", self.evaluation.execution_map()["topology-foreign-context"].issue_codes)
        causal = self.evaluation.execution_map()["causal-positive"]
        self.assertEqual(causal.state, "complete")
        self.assertGreaterEqual(len(causal.output["alternative_edge_ids"]), 2)
        self.assertEqual(self.evaluation.execution_map()["causal-contradiction"].state, "contradictory")

    def test_posterior_and_table_states_remain_visible(self) -> None:
        posterior = self.evaluation.execution_map()["posterior-positive"]
        self.assertEqual(posterior.state, "supported")
        self.assertTrue(posterior.output["is_reconciled"])
        self.assertEqual(posterior.output["residual"], 0.0)
        foreign = self.evaluation.execution_map()["posterior-foreign-component"]
        self.assertEqual(foreign.state, "partial")
        self.assertIn("foreign_component", foreign.issue_codes)
        table = self.evaluation.execution_map()["table-positive"]
        self.assertEqual(table.state, "partial")
        self.assertEqual(table.output["total_matches"], 3)
        self.assertIn("pagination_applied", self.evaluation.execution_map()["table-pagination"].issue_codes)

    def test_quality_runtime_replay_and_invariants(self) -> None:
        runtime = run_beta_frontier_runtime(self.fixture, run_id="test-beta-frontier")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 8)
        self.assertTrue(runtime.quality.accepted)
        self.assertTrue(runtime.reconciliation.reconciled)
        self.assertTrue(beta_frontier_replay_is_deterministic(self.fixture))
        self.assertTrue(run_beta_frontier_invariants(self.fixture, self.evaluation).accepted)
        self.assertTrue(audit_beta_frontier_depth().accepted)
        self.assertEqual(len(replay_beta_frontier(self.fixture).execution_addresses), 16)

    def test_review_and_release_artifacts_are_complete(self) -> None:
        runtime = run_beta_frontier_runtime(self.fixture, run_id="test-beta-review")
        replay = replay_beta_frontier(self.fixture, replay_id="test-beta-review-replay")
        release = build_beta_frontier_release_manifest(runtime.bundle, runtime.quality, replay, runtime)
        self.assertEqual(release.state.value, "ready")
        policy = default_beta_frontier_policy()
        view = build_beta_frontier_review_view(self.fixture, self.evaluation, policy.decide(self.evaluation), release)
        queue = build_beta_frontier_review_queue(self.fixture, self.evaluation, policy.decide(self.evaluation), view, release)
        self.assertEqual(view.ready_count, 3)
        self.assertEqual(view.held_count, 10)
        self.assertEqual(len(queue.items), 13)
        self.assertTrue(all(item.priority.value <= 4 for item in queue.items))
        inventory = build_beta_frontier_artifact_inventory(self.fixture.fixture_id, self.fixture.content_address, self.evaluation, runtime.metrics, runtime.quality, runtime, runtime.bundle, release)
        self.assertTrue(inventory.accepted)
        self.assertEqual({item.kind for item in inventory.artifacts}, set(BetaFrontierArtifactKind))

    def test_schema_scenarios_thresholds_and_metrics_are_deterministic(self) -> None:
        schema = default_beta_frontier_schema()
        self.assertEqual(len(schema.operations), 4)
        self.assertIn("residual", schema.field_names())
        scenarios = build_beta_frontier_scenario_matrix()
        self.assertEqual(len(scenarios.scenarios), 32)
        self.assertEqual(len(scenarios.dimensions), 8)
        thresholds = build_beta_frontier_threshold_report()
        self.assertEqual(len(thresholds.profiles), 6)
        self.assertEqual(len(thresholds.probes), 42)
        metrics = measure_beta_frontier(self.evaluation)
        self.assertEqual(len(metrics.metrics), 13)
        self.assertEqual(metrics.by_id("positive_acceptance_rate").value, 1.0)

    def test_observability_retains_issue_events(self) -> None:
        runtime = run_beta_frontier_runtime(self.fixture, run_id="test-beta-observability")
        report = observe_beta_frontier(runtime)
        self.assertGreater(len(report.events), len(runtime.stages))
        self.assertGreater(report.state_counts.get("partial", 0), 0)
        self.assertGreater(len(report.events_for("issue_retained")), 0)
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_serialized_projection_audit_boundaries_and_runbook(self) -> None:
        projection_audit = audit_beta_frontier_projections(self.evaluation)
        self.assertTrue(projection_audit.accepted)
        self.assertGreaterEqual(projection_audit.passed_count, 100)
        self.assertGreater(len(projection_audit.for_operation(BetaFrontierOperation.CAUSAL_CHAIN)), 10)
        accessibility = evaluate_beta_frontier_accessibility(self.fixture, self.evaluation)
        self.assertTrue(accessibility.accepted)
        self.assertGreaterEqual(accessibility.passed_count, 35)
        boundary = evaluate_beta_frontier_boundary(self.fixture, self.evaluation)
        self.assertTrue(boundary.accepted)
        self.assertEqual(boundary.passed_count, 15)
        runbook = default_beta_frontier_runbook()
        self.assertEqual(runbook.required_step_count, 25)
        self.assertEqual(len(runbook.by_phase("close")), 4)
        self.assertTrue(all(step.expected_exit == 0 for step in runbook.steps))

    def test_cross_surface_validation_matrix_keeps_review_bands(self) -> None:
        report = build_beta_frontier_validation_matrix(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.axes), 8)
        self.assertEqual(len(report.cases), 128)
        self.assertGreater(report.pass_count, 0)
        self.assertGreater(report.review_count, 0)
        self.assertGreater(report.hold_count, 0)
        self.assertTrue(any(item.status is BetaFrontierValidationStatus.HOLD for item in report.cases))
        self.assertEqual(len(report.for_operation(BetaFrontierOperation.EVIDENCE_TABLE)), 32)


if __name__ == "__main__":
    unittest.main()
