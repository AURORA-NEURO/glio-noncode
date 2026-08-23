from __future__ import annotations

import unittest

from glio_noncode.validation_design_frontier_contracts import ValidationDesignOperation, ValidationDesignRole, ValidationDesignState
from glio_noncode.validation_design_frontier_fixture_eval import evaluate_validation_design_fixture
from glio_noncode.validation_design_frontier_operations import evaluate_assay_eligibility, evaluate_gap_analysis, evaluate_mpra_package, evaluate_starrseq_package
from glio_noncode.validation_design_frontier_public_data import audit_validation_design_frontier_data, default_validation_design_frontier_fixture
from glio_noncode.validation_design_frontier_runtime import run_validation_design_runtime


class ValidationDesignFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_validation_design_frontier_fixture()
        cls.audit = audit_validation_design_frontier_data(cls.fixture)
        cls.evaluation = evaluate_validation_design_fixture(cls.fixture)

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

    def test_positive_states(self) -> None:
        expected = {ValidationDesignOperation.GAP_ANALYSIS: ValidationDesignState.READY, ValidationDesignOperation.ASSAY_ELIGIBILITY: ValidationDesignState.ROUTED, ValidationDesignOperation.MPRA_PACKAGE: ValidationDesignState.PACKAGED, ValidationDesignOperation.STARRSEQ_PACKAGE: ValidationDesignState.PACKAGED}
        for record in self.fixture.positive_records:
            execution = next(row for row in self.evaluation.executions if row.record_id == record.record_id)
            self.assertEqual(execution.observed_state, expected[record.operation])
            self.assertEqual(execution.issue_codes, ())

    def test_controls_keep_failure_boundaries(self) -> None:
        for record in self.fixture.control_records:
            execution = next(row for row in self.evaluation.executions if row.record_id == record.record_id)
            self.assertEqual(record.role, ValidationDesignRole.CONTROL)
            self.assertEqual(execution.observed_state, record.expected_state)
            self.assertTrue(set(record.expected_issue_codes) <= set(execution.issue_codes))

    def test_gap_analysis_marks_missing_dimensions(self) -> None:
        payload = self.fixture.records[1].payload
        result = evaluate_gap_analysis(payload)
        self.assertEqual(result.state, ValidationDesignState.REVIEW)
        self.assertIn("gap_dimensions", result.issue_codes)
        self.assertEqual(result.output["gap_count"], 1)

    def test_assay_route_requires_supported_match(self) -> None:
        payload = self.fixture.records[5].payload
        result = evaluate_assay_eligibility(payload)
        self.assertEqual(result.state, ValidationDesignState.REVIEW)
        self.assertIn("assay_unsupported", result.issue_codes)

    def test_mpra_and_starr_controls(self) -> None:
        mpra = evaluate_mpra_package(self.fixture.records[9].payload)
        starr = evaluate_starrseq_package(self.fixture.records[13].payload)
        self.assertIn("allele_unchanged", mpra.issue_codes)
        self.assertIn("construct_field_missing", starr.issue_codes)

    def test_runtime_closes_all_stages(self) -> None:
        runtime = run_validation_design_runtime(self.fixture, run_id="validation-design-test")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 79)
        self.assertTrue(runtime.replay.deterministic)
        self.assertTrue(runtime.planes["bundle"].accepted)
        self.assertEqual(runtime.stage_ids[0], "data-audit")
        self.assertEqual(runtime.stage_ids[-1], "observability")


if __name__ == "__main__":
    unittest.main()
