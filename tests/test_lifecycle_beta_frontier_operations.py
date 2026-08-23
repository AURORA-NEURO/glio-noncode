from __future__ import annotations

import unittest

from glio_noncode.lifecycle_beta_frontier_adapters import build_lifecycle_beta_frontier_adapters
from glio_noncode.lifecycle_beta_frontier_contracts import LifecycleBetaFrontierOperation, LifecycleBetaFrontierState
from glio_noncode.lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_handoff import build_lifecycle_beta_frontier_handoff
from glio_noncode.lifecycle_beta_frontier_metrics import measure_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_public_data import default_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_scenario_matrix import evaluate_lifecycle_beta_frontier_scenarios
from glio_noncode.lifecycle_beta_frontier_thresholds import build_lifecycle_beta_frontier_threshold_report
from glio_noncode.lifecycle_beta_frontier_validation_matrix import build_lifecycle_beta_frontier_validation_matrix
from glio_noncode.lifecycle_beta_frontier_views import build_lifecycle_beta_frontier_view


class LifecycleBetaFrontierOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_lifecycle_beta_frontier_fixture()
        self.evaluation = evaluate_lifecycle_beta_frontier_fixture(self.fixture)
        self.metrics = measure_lifecycle_beta_frontier(self.evaluation)

    def test_operation_enum_is_complete(self) -> None:
        self.assertEqual(len(tuple(LifecycleBetaFrontierOperation)), 8)
        self.assertEqual({item.operation for item in self.metrics.operation_metrics}, set(LifecycleBetaFrontierOperation))

    def test_each_operation_has_four_execution_receipts(self) -> None:
        for operation in LifecycleBetaFrontierOperation:
            self.assertEqual(len(self.evaluation.by_operation(operation)), 4)

    def test_tier_surface_preserves_contradiction(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C05-CTRL-001")
        self.assertIs(item.state, LifecycleBetaFrontierState.CONTRADICTORY)
        self.assertIn("tier_direction_conflict", item.issue_codes)

    def test_lineage_surface_preserves_missing_parent(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C06-CTRL-001")
        self.assertIs(item.state, LifecycleBetaFrontierState.PARTIAL)
        self.assertIn("missing_parent", item.issue_codes)

    def test_uncertainty_surface_preserves_foreign_context(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C07-CTRL-001")
        self.assertIs(item.state, LifecycleBetaFrontierState.OUT_OF_DOMAIN)
        self.assertIn("context_mismatch", item.issue_codes)

    def test_routing_surface_preserves_priority(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C08-POS-001")
        self.assertIs(item.state, LifecycleBetaFrontierState.CONTRADICTORY)
        self.assertGreaterEqual(len(item.output["assignments"]), 2)
        self.assertGreaterEqual(item.output["assignments"][0]["priority"], item.output["assignments"][1]["priority"])

    def test_blinded_surface_preserves_split_decision(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C09-CTRL-001")
        self.assertIs(item.state, LifecycleBetaFrontierState.SPLIT_DECISION)
        self.assertIn("split_verdict", item.issue_codes)

    def test_comment_surface_preserves_append_issue(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C10-CTRL-001")
        self.assertIs(item.state, LifecycleBetaFrontierState.PARTIAL)
        self.assertIn("duplicate_log_id", item.issue_codes)

    def test_release_surface_preserves_rejection(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C11-CTRL-002")
        self.assertIs(item.state, LifecycleBetaFrontierState.REJECTED)
        self.assertIn("explicit_rejection", item.issue_codes)

    def test_delta_surface_preserves_change_classes(self) -> None:
        item = next(item for item in self.evaluation.executions if item.record_id == "C12-POS-001")
        self.assertIs(item.state, LifecycleBetaFrontierState.REVIEW_REQUIRED)
        self.assertEqual(set(item.issue_codes), {"claim_added", "claim_changed", "citation_changed"})

    def test_scenario_matrix_conserves_all_operations(self) -> None:
        matrix = evaluate_lifecycle_beta_frontier_scenarios(self.evaluation)
        self.assertTrue(matrix.accepted)
        for operation in LifecycleBetaFrontierOperation:
            self.assertEqual(len(matrix.by_operation(operation)), 4)

    def test_validation_matrix_conserves_all_records(self) -> None:
        matrix = build_lifecycle_beta_frontier_validation_matrix(self.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len({item.record_id for item in matrix.cells}), 32)

    def test_thresholds_conserve_all_operations(self) -> None:
        report = build_lifecycle_beta_frontier_threshold_report()
        for operation in LifecycleBetaFrontierOperation:
            self.assertEqual(len(report.by_operation(operation)), 5)

    def test_view_filters_positive_rows(self) -> None:
        view = build_lifecycle_beta_frontier_view(self.evaluation)
        positives = tuple(item for item in view.entries if item.role.value == "positive")
        self.assertEqual(len(positives), 8)

    def test_handoff_sources_are_bound_per_operation(self) -> None:
        handoff = build_lifecycle_beta_frontier_handoff(self.fixture, self.evaluation, self.metrics)
        for operation in LifecycleBetaFrontierOperation:
            self.assertTrue(handoff.item(operation).source_ids)

    def test_adapter_contracts_have_operation_specific_inputs(self) -> None:
        registry = build_lifecycle_beta_frontier_adapters()
        self.assertEqual(len({item.input_contract for item in registry.specs}), 8)
        self.assertEqual(len({item.output_contract for item in registry.specs}), 8)


if __name__ == "__main__":
    unittest.main()
