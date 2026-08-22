"""Depth and contract coverage for Domain 15 C01–C04."""

from __future__ import annotations

import unittest

from glio_noncode.workspace_frontier_adapters import default_workspace_frontier_adapters
from glio_noncode.workspace_frontier_artifacts import build_workspace_frontier_artifact_inventory
from glio_noncode.workspace_frontier_checks import workspace_frontier_invariants_from_execution
from glio_noncode.workspace_frontier_contracts import default_workspace_frontier_contracts
from glio_noncode.workspace_frontier_depth import audit_workspace_frontier_depth
from glio_noncode.workspace_frontier_fixture_eval import evaluate_workspace_frontier_fixture
from glio_noncode.workspace_frontier_lineage import build_workspace_frontier_lineage
from glio_noncode.workspace_frontier_metrics import measure_workspace_frontier
from glio_noncode.workspace_frontier_policy import default_workspace_frontier_policy
from glio_noncode.workspace_frontier_public_data import (
    WorkspaceFrontierOperation,
    default_workspace_frontier_fixture,
)
from glio_noncode.workspace_frontier_quality_gate import evaluate_workspace_frontier_quality
from glio_noncode.workspace_frontier_reconciliation import reconcile_workspace_frontier
from glio_noncode.workspace_frontier_release import build_workspace_frontier_release_manifest
from glio_noncode.workspace_frontier_replay import replay_workspace_frontier
from glio_noncode.workspace_frontier_review_queue import build_workspace_frontier_review_queue
from glio_noncode.workspace_frontier_runtime import run_workspace_frontier_runtime
from glio_noncode.workspace_frontier_scenario_matrix import build_workspace_frontier_scenario_matrix
from glio_noncode.workspace_frontier_schema import default_workspace_frontier_schema
from glio_noncode.workspace_frontier_thresholds import build_workspace_frontier_threshold_report
from glio_noncode.workspace_frontier_views import build_workspace_frontier_review_view


class WorkspaceFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_workspace_frontier_fixture()
        self.evaluation = evaluate_workspace_frontier_fixture(self.fixture)
        self.policy = default_workspace_frontier_policy()
        self.decisions = self.policy.decide(self.evaluation)
        self.lineage = build_workspace_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_workspace_frontier(self.fixture, self.evaluation, self.policy)
        self.metrics = measure_workspace_frontier(self.evaluation)
        self.quality = evaluate_workspace_frontier_quality(self.fixture, self.evaluation, default_workspace_frontier_contracts(), default_workspace_frontier_schema(), self.lineage, self.reconciliation)
        self.runtime = run_workspace_frontier_runtime(self.fixture)
        self.release = build_workspace_frontier_release_manifest(self.runtime.bundle, self.quality, replay_workspace_frontier(self.fixture), self.runtime)
        self.view = build_workspace_frontier_review_view(self.fixture, self.evaluation, self.decisions, self.release)
        self.queue = build_workspace_frontier_review_queue(self.fixture, self.evaluation, self.decisions, self.view, self.release)

    def test_depth_audit_has_twenty_passing_checks(self) -> None:
        audit = audit_workspace_frontier_depth(self.fixture, self.evaluation, self.metrics, self.reconciliation, self.runtime)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 21)
        self.assertEqual(audit.passed_count, 21)
        self.assertEqual(audit.failed_check_ids, ())

    def test_each_surface_has_one_positive_and_three_controls(self) -> None:
        for operation in WorkspaceFrontierOperation:
            records = tuple(item for item in self.fixture.records if item.operation is operation)
            self.assertEqual(len(records), 4)
            self.assertEqual(sum(item.role.value == "positive" for item in records), 1)
            self.assertEqual(sum(item.role.value == "control" for item in records), 3)

    def test_runtime_stage_addresses_form_a_complete_chain(self) -> None:
        self.assertEqual(tuple(stage.sequence for stage in self.runtime.stages), tuple(range(1, 9)))
        self.assertTrue(all(stage.output_address for stage in self.runtime.stages))
        self.assertTrue(all(stage.content_address.startswith("sha256:") for stage in self.runtime.stages))
        self.assertEqual(self.runtime.stages[-1].stage_id, "bundle-assembly")

    def test_quality_gate_checks_context_and_accessibility(self) -> None:
        identifiers = {item.check_id for item in self.quality.checks}
        self.assertIn("context:exact", identifiers)
        self.assertIn("accessibility:retained", identifiers)
        self.assertEqual(len(identifiers), 14)
        self.assertTrue(self.quality.accepted)

    def test_invariant_projection_is_accepted(self) -> None:
        report = workspace_frontier_invariants_from_execution(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.results), 10)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in report.results))

    def test_review_queue_has_explicit_dispositions(self) -> None:
        self.assertTrue(self.queue.accepted)
        self.assertEqual(len(self.queue.ready_items), 3)
        self.assertEqual(len(self.queue.held_items), 13)
        self.assertEqual(len(self.queue.items), 16)
        self.assertEqual(len(self.queue.checks), 6)

    def test_threshold_report_is_large_but_bounded(self) -> None:
        report = build_workspace_frontier_threshold_report()
        self.assertEqual(len(report.profiles), 4)
        self.assertEqual(len(report.probes), 972)
        self.assertTrue(report.accepted_probe_ids)
        self.assertTrue(report.review_probe_ids)
        self.assertTrue(all(item.page_limit <= 50 for item in report.probes))

    def test_scenario_matrix_spans_all_dimensions(self) -> None:
        matrix = build_workspace_frontier_scenario_matrix()
        self.assertEqual(matrix.dimensions, ("operation", "context_mode", "data_mode", "access_mode", "expected_state", "review_required"))
        self.assertEqual(len(matrix.scenarios), 33)
        self.assertTrue(all(matrix.by_operation[item.value] > 0 for item in WorkspaceFrontierOperation))

    def test_adapter_registry_is_one_to_one_with_surfaces(self) -> None:
        registry = default_workspace_frontier_adapters()
        self.assertEqual({item.operation for item in registry.adapters}, set(WorkspaceFrontierOperation))
        self.assertEqual(len({item.adapter_id for item in registry.adapters}), 4)

    def test_artifact_inventory_is_rooted_at_release(self) -> None:
        inventory = build_workspace_frontier_artifact_inventory(self.fixture.fixture_id, self.fixture.content_address, self.evaluation, self.metrics, self.quality, self.runtime, self.runtime.bundle, self.release)
        self.assertEqual(inventory.root_artifact_id, "workspace-artifact-release")
        self.assertEqual(len(inventory.artifacts), 7)
        self.assertTrue(all(item.public for item in inventory.artifacts))


if __name__ == "__main__":
    unittest.main()
