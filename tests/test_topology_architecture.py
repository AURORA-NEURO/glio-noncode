"""Comprehensive tests for the D09 3D genome and regulatory topology aggregate."""

from __future__ import annotations

import unittest

from glio_noncode.topology_architecture_audit import deep_audit_topology_architecture
from glio_noncode.topology_architecture_compliance import (
    assess_topology_architecture_compliance,
)
from glio_noncode.topology_architecture_contract_matrix import (
    build_topology_architecture_contract_matrix,
    topology_architecture_contract_matrix_is_closed,
    topology_architecture_contract_matrix_summary,
)
from glio_noncode.topology_architecture_controls import (
    topology_architecture_control_coverage,
    topology_architecture_controls_are_closed,
)
from glio_noncode.topology_architecture_depth import (
    assess_topology_architecture_depth,
    topology_architecture_depth_percent,
)
from glio_noncode.topology_architecture_ledger import (
    build_topology_architecture_ledger,
    topology_architecture_ledger_is_closed,
)
from glio_noncode.topology_architecture_lineage import (
    build_topology_architecture_lineage,
    topology_architecture_lineage_gaps,
)
from glio_noncode.topology_architecture_metrics import (
    topology_architecture_metric_invariants,
    topology_architecture_metrics,
)
from glio_noncode.topology_architecture_operations import (
    evaluate_topology_architecture_fixture,
)
from glio_noncode.topology_architecture_plan import (
    build_topology_architecture_plan,
    topology_architecture_operation_order,
)
from glio_noncode.topology_architecture_public_data import (
    audit_topology_architecture_data,
    default_topology_architecture_fixture,
)
from glio_noncode.topology_architecture_query import query_topology_architecture_cases
from glio_noncode.topology_architecture_replay import replay_topology_architecture_fixture
from glio_noncode.topology_architecture_review import build_topology_architecture_review_queue
from glio_noncode.topology_architecture_runtime import run_topology_architecture
from glio_noncode.topology_architecture_schema import (
    topology_architecture_schema_descriptor,
    validate_topology_architecture_fixture,
)


class TopologyArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_topology_architecture_fixture()
        cls.evaluation = evaluate_topology_architecture_fixture(cls.fixture)

    def test_fixture_has_four_families_and_closed_cardinality(self) -> None:
        self.assertEqual(len(self.fixture.sources), 17)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertEqual(len({item.family for item in self.fixture.operations}), 4)

    def test_data_audit_schema_and_joins_pass(self) -> None:
        audit = audit_topology_architecture_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(tuple(item.check_id for item in audit.checks if not item.passed), ())
        self.assertTrue(validate_topology_architecture_fixture(self.fixture))
        self.assertEqual(topology_architecture_schema_descriptor()["operation_count"], 16)

    def test_evaluation_runs_all_operations_and_real_state_paths(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 392)
        positives = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "accepted"
        }
        self.assertEqual(len(positives), 16)
        self.assertTrue(
            all(item.observed_result_state == "supported" for item in positives.values())
        )

    def test_controls_hold_context_input_and_identity(self) -> None:
        controls = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "review"
        }
        self.assertEqual(len(controls), 48)
        self.assertEqual(
            controls["D09-C01-foreign_context"].observed_issue_codes,
            ("context_mismatch",),
        )
        self.assertEqual(
            controls["D09-C08-malformed_input"].observed_result_state,
            "invalid",
        )
        self.assertEqual(
            controls["D09-C16-identity_conflict"].observed_result_state,
            "contradictory",
        )

    def test_plan_review_lineage_ledger_and_metrics_close(self) -> None:
        plan = build_topology_architecture_plan(self.fixture)
        review = build_topology_architecture_review_queue(self.evaluation)
        lineage = build_topology_architecture_lineage(self.fixture)
        ledger = build_topology_architecture_ledger(self.fixture, self.evaluation)
        metrics = topology_architecture_metrics(self.fixture, self.evaluation)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(topology_architecture_operation_order(plan)), 16)
        self.assertEqual(len(review.items), 48)
        self.assertEqual(sum(len(item) for item in lineage["operation_cases"].values()), 64)
        self.assertEqual(topology_architecture_lineage_gaps(self.fixture), ())
        self.assertTrue(topology_architecture_ledger_is_closed(ledger))
        self.assertEqual(metrics["receipt_pass_rate"], 1.0)
        self.assertEqual(topology_architecture_metric_invariants(metrics), ())

    def test_runtime_release_depth_compliance_and_replay_close(self) -> None:
        runtime = run_topology_architecture(self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 22)
        self.assertEqual(len(runtime.artifacts), 6)
        self.assertEqual(runtime.release.state.value, "published")
        self.assertEqual(runtime.stages[-1].stage_id, "observability-closed")
        self.assertTrue(replay_topology_architecture_fixture(self.fixture).accepted)
        self.assertTrue(assess_topology_architecture_compliance(self.fixture)["accepted"])
        depth = assess_topology_architecture_depth(self.fixture, self.evaluation)
        self.assertEqual(topology_architecture_depth_percent(depth), 100.0)

    def test_query_contract_matrix_controls_and_deep_audit_close(self) -> None:
        runtime = run_topology_architecture(self.fixture)
        rows = query_topology_architecture_cases(runtime, operation_id="D09-C13")
        self.assertEqual(len(rows), 4)
        matrix = build_topology_architecture_contract_matrix(self.fixture)
        summary = topology_architecture_contract_matrix_summary(matrix)
        self.assertTrue(topology_architecture_contract_matrix_is_closed(self.fixture))
        self.assertTrue(topology_architecture_controls_are_closed(self.fixture, self.evaluation))
        self.assertEqual(summary["operation_count"], 16)
        self.assertEqual(
            topology_architecture_control_coverage(self.fixture, self.evaluation)["held_paths"], 48
        )
        self.assertTrue(all(deep_audit_topology_architecture(self.fixture)["checks"].values()))


if __name__ == "__main__":
    unittest.main()
