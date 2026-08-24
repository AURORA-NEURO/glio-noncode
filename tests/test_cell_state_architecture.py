"""Comprehensive tests for the D08 cell-state architecture aggregate."""

from __future__ import annotations

import unittest

from glio_noncode.cell_state_architecture_compliance import (
    assess_cell_state_architecture_compliance,
)
from glio_noncode.cell_state_architecture_depth import (
    assess_cell_state_architecture_depth,
    depth_percent,
)
from glio_noncode.cell_state_architecture_invariants import cell_state_architecture_invariants
from glio_noncode.cell_state_architecture_ledger import (
    build_cell_state_architecture_ledger,
    verify_ledger,
)
from glio_noncode.cell_state_architecture_lineage import (
    build_cell_state_architecture_lineage,
    lineage_gaps,
)
from glio_noncode.cell_state_architecture_metrics import (
    cell_state_architecture_metrics,
    metric_invariants,
)
from glio_noncode.cell_state_architecture_operations import evaluate_cell_state_architecture_fixture
from glio_noncode.cell_state_architecture_plan import (
    build_cell_state_architecture_plan,
    plan_operation_order,
)
from glio_noncode.cell_state_architecture_policy import policy_matrix
from glio_noncode.cell_state_architecture_public_data import (
    audit_cell_state_architecture_data,
    default_cell_state_architecture_fixture,
)
from glio_noncode.cell_state_architecture_query import find_cell_state_cases
from glio_noncode.cell_state_architecture_replay import replay_cell_state_architecture_fixture
from glio_noncode.cell_state_architecture_review import build_cell_state_architecture_review_queue
from glio_noncode.cell_state_architecture_runtime import run_cell_state_architecture
from glio_noncode.cell_state_architecture_scenarios import cell_state_architecture_scenario_matrix
from glio_noncode.cell_state_architecture_schema import (
    schema_descriptor,
    validate_cell_state_architecture_fixture,
)
from glio_noncode.cell_state_architecture_validation import validate_cell_state_architecture


class CellStateArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_cell_state_architecture_fixture()
        cls.evaluation = evaluate_cell_state_architecture_fixture(cls.fixture)

    def test_fixture_has_four_families_and_closed_cardinality(self) -> None:
        self.assertEqual(len(self.fixture.sources), 18)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertEqual(len({item.family for item in self.fixture.operations}), 4)
        self.assertTrue(all(item.public_aggregate for item in self.fixture.sources))
        self.assertTrue(all(item.delegate_context_key for item in self.fixture.cases))

    def test_data_audit_schema_and_joins_pass(self) -> None:
        audit = audit_cell_state_architecture_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertTrue(validate_cell_state_architecture_fixture(self.fixture))
        self.assertEqual(schema_descriptor()["operation_count"], 16)

    def test_evaluation_runs_all_operations_and_real_state_paths(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 458)
        positives = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "accepted"
        }
        self.assertEqual(positives["D08-C13-positive"].observed_result_state, "accepted")
        self.assertEqual(positives["D08-C14-positive"].observed_result_state, "accepted")
        self.assertEqual(positives["D08-C15-positive"].observed_result_state, "accepted")
        self.assertEqual(positives["D08-C16-positive"].observed_result_state, "published")
        abundance = next(
            item for item in self.evaluation.executions if item.case_id == "D08-C13-positive"
        )
        self.assertEqual(abundance.summary["stable_ids"], ["aggregate-sample-a:stem_like"])
        mapping = next(
            item for item in self.evaluation.executions if item.case_id == "D08-C14-positive"
        )
        self.assertEqual(mapping.summary["mapped_ids"], ["aggregate-cell-001"])

    def test_controls_hold_context_input_and_identity(self) -> None:
        controls = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "review"
        }
        self.assertEqual(len(controls), 48)
        self.assertEqual(
            controls["D08-C01-foreign_context"].observed_issue_codes, ("context_mismatch",)
        )
        self.assertEqual(controls["D08-C08-malformed_input"].observed_result_state, "invalid")
        self.assertEqual(
            controls["D08-C16-identity_conflict"].observed_result_state, "contradictory"
        )

    def test_plan_review_lineage_ledger_and_metrics_close(self) -> None:
        plan = build_cell_state_architecture_plan(self.fixture)
        review = build_cell_state_architecture_review_queue(self.evaluation)
        lineage = build_cell_state_architecture_lineage(self.fixture)
        ledger = build_cell_state_architecture_ledger(self.fixture, self.evaluation)
        metrics = cell_state_architecture_metrics(self.fixture, self.evaluation)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan_operation_order(plan)), 16)
        self.assertEqual(len(review.items), 48)
        self.assertEqual(lineage["case_count"], 64)
        self.assertEqual(lineage_gaps(self.fixture), ())
        self.assertTrue(verify_ledger(ledger))
        self.assertEqual(metrics["receipt_pass_rate"], 1.0)
        self.assertEqual(metric_invariants(metrics), ())

    def test_runtime_release_depth_compliance_and_replay_close(self) -> None:
        runtime = run_cell_state_architecture(self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 24)
        self.assertEqual(len(runtime.artifacts), 6)
        self.assertEqual(runtime.release.state.value, "published")
        self.assertEqual(len(runtime.quality.checks), 12)
        self.assertTrue(runtime.quality.accepted)
        self.assertEqual(runtime.depth.check_count, 458)
        self.assertEqual(runtime.depth.state_count, 6)
        self.assertEqual(runtime.stages[-1].stage_id, "runtime-finalized")
        self.assertTrue(replay_cell_state_architecture_fixture(self.fixture).accepted)
        self.assertTrue(assess_cell_state_architecture_compliance(self.fixture)["accepted"])
        depth = assess_cell_state_architecture_depth(self.fixture, self.evaluation)
        self.assertEqual(depth_percent(depth), 100.0)

    def test_query_scenarios_invariants_and_validation(self) -> None:
        runtime = run_cell_state_architecture(self.fixture)
        rows = find_cell_state_cases(runtime, operation_id="D08-C13")
        self.assertEqual(len(rows), 4)
        matrix = cell_state_architecture_scenario_matrix(self.fixture)
        self.assertEqual([item["case_count"] for item in matrix], [16, 16, 16, 16])
        self.assertEqual(metric_invariants(cell_state_architecture_metrics(self.fixture)), ())
        self.assertTrue(all(cell_state_architecture_invariants(self.fixture).values()))
        self.assertTrue(validate_cell_state_architecture(self.fixture)["accepted"])
        self.assertEqual(len(policy_matrix()), 4)


if __name__ == "__main__":
    unittest.main()
