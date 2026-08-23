from __future__ import annotations

import unittest

from glio_noncode.editing_design_frontier_contracts import EditingDesignOperation, EditingDesignRole, EditingDesignState
from glio_noncode.editing_design_frontier_fixture_eval import evaluate_editing_design_fixture
from glio_noncode.editing_design_frontier_operations import evaluate_allele_reporter, evaluate_base_editing, evaluate_crispr_design, evaluate_prime_editing
from glio_noncode.editing_design_frontier_public_data import audit_editing_design_frontier_data, default_editing_design_frontier_fixture
from glio_noncode.editing_design_frontier_runtime import run_editing_design_runtime


class EditingDesignFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_editing_design_frontier_fixture()
        cls.audit = audit_editing_design_frontier_data(cls.fixture)
        cls.evaluation = evaluate_editing_design_fixture(cls.fixture)

    def test_public_fixture_shape(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)

    def test_evaluation_has_five_checks_per_row(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 80)
        self.assertEqual(self.evaluation.failed_checks, 0)

    def test_positive_operations_are_designed(self) -> None:
        expected = {EditingDesignOperation.CRISPR_DESIGN: "D13-C05-POS-001", EditingDesignOperation.BASE_EDITING: "D13-C06-POS-001", EditingDesignOperation.PRIME_EDITING: "D13-C07-POS-001", EditingDesignOperation.ALLELE_REPORTER: "D13-C08-POS-001"}
        for operation, record_id in expected.items():
            execution = next(row for row in self.evaluation.executions if row.record_id == record_id)
            self.assertEqual(execution.operation, operation)
            self.assertEqual(execution.observed_state, EditingDesignState.DESIGNED)
            self.assertEqual(execution.issue_codes, ())

    def test_controls_preserve_hold_reasons(self) -> None:
        for record in self.fixture.control_records:
            execution = next(row for row in self.evaluation.executions if row.record_id == record.record_id)
            self.assertEqual(record.role, EditingDesignRole.CONTROL)
            self.assertEqual(execution.observed_state, record.expected_state)
            self.assertTrue(set(record.expected_issue_codes) <= set(execution.issue_codes))

    def test_crispr_mode_and_target_controls(self) -> None:
        self.assertEqual(evaluate_crispr_design(self.fixture.records[0].payload).state, EditingDesignState.DESIGNED)
        self.assertIn("mode_unsupported", evaluate_crispr_design(self.fixture.records[1].payload).issue_codes)
        self.assertIn("targets_missing", evaluate_crispr_design(self.fixture.records[2].payload).issue_codes)

    def test_base_editing_controls(self) -> None:
        self.assertEqual(evaluate_base_editing(self.fixture.records[4].payload).state, EditingDesignState.DESIGNED)
        self.assertIn("substitution_not_single_base", evaluate_base_editing(self.fixture.records[6].payload).issue_codes)

    def test_prime_editing_controls(self) -> None:
        self.assertEqual(evaluate_prime_editing(self.fixture.records[8].payload).state, EditingDesignState.DESIGNED)
        self.assertIn("edit_length_exceeded", evaluate_prime_editing(self.fixture.records[10].payload).issue_codes)
        self.assertIn("flank_shortage", evaluate_prime_editing(self.fixture.records[11].payload).issue_codes)

    def test_reporter_pair_and_budget_controls(self) -> None:
        self.assertEqual(evaluate_allele_reporter(self.fixture.records[12].payload).state, EditingDesignState.DESIGNED)
        self.assertIn("constructs_missing", evaluate_allele_reporter(self.fixture.records[14].payload).issue_codes)
        self.assertIn("construct_budget_exceeded", evaluate_allele_reporter(self.fixture.records[15].payload).issue_codes)

    def test_runtime_closes_all_planes(self) -> None:
        runtime = run_editing_design_runtime(self.fixture, run_id="editing-design-test")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 79)
        self.assertEqual(len(runtime.planes), 70)
        self.assertEqual(len(runtime.stage_ids), len(set(runtime.stage_ids)))
        self.assertEqual(runtime.stage_ids[0], "data-audit")


if __name__ == "__main__":
    unittest.main()
