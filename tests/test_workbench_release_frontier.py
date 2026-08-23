from __future__ import annotations

import unittest

from glio_noncode.workbench_release_frontier_contracts import WorkbenchReleaseOperation, WorkbenchReleaseRole, WorkbenchReleaseState
from glio_noncode.workbench_release_frontier_fixture_eval import audit_workbench_release_context, evaluate_workbench_release_fixture
from glio_noncode.workbench_release_frontier_operations import evaluate_accessibility, evaluate_report_export, evaluate_review_form, evaluate_search_palette, run_workbench_release_operation
from glio_noncode.workbench_release_frontier_public_data import audit_workbench_release_frontier_data, default_workbench_release_frontier_fixture
from glio_noncode.workbench_release_frontier_runtime import run_workbench_release_runtime


class WorkbenchReleaseFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_workbench_release_frontier_fixture()
        cls.audit = audit_workbench_release_frontier_data(cls.fixture)
        cls.evaluation = evaluate_workbench_release_fixture(cls.fixture)

    def test_public_fixture_shape(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(audit_workbench_release_context(self.fixture), ("GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment",))

    def test_evaluation_has_five_checks_per_row(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 80)
        self.assertEqual(self.evaluation.failed_checks, 0)

    def test_positive_states(self) -> None:
        expected = {WorkbenchReleaseOperation.REVIEW_FORM: WorkbenchReleaseState.REVIEWED, WorkbenchReleaseOperation.REPORT_EXPORT: WorkbenchReleaseState.EXPORTED, WorkbenchReleaseOperation.SEARCH_PALETTE: WorkbenchReleaseState.SEARCHED, WorkbenchReleaseOperation.ACCESSIBILITY: WorkbenchReleaseState.PASSED}
        for record in self.fixture.positive_records:
            result = run_workbench_release_operation(record.operation, record.payload)
            self.assertEqual(result.state, expected[record.operation])
            self.assertEqual(result.issue_codes, ())

    def test_controls_keep_failure_boundaries(self) -> None:
        for record in self.fixture.control_records:
            execution = next(row for row in self.evaluation.executions if row.record_id == record.record_id)
            self.assertEqual(record.role, WorkbenchReleaseRole.CONTROL)
            self.assertEqual(execution.observed_state, record.expected_state)
            self.assertTrue(set(record.expected_issue_codes) <= set(execution.issue_codes))

    def test_form_and_export_operations(self) -> None:
        form = self.fixture.records[0].payload
        self.assertEqual(evaluate_review_form(form | {"response": {"decision": "accept"}}).state, WorkbenchReleaseState.REVIEW)
        export = self.fixture.records[4].payload
        duplicate = [export["sections"][0], {**export["sections"][1], "section_id": export["sections"][0]["section_id"]}]
        self.assertIn("duplicate_section_id", evaluate_report_export(export | {"sections": duplicate}).issue_codes)

    def test_search_and_accessibility_operations(self) -> None:
        search = self.fixture.records[8].payload
        self.assertEqual(evaluate_search_palette(search).state, WorkbenchReleaseState.SEARCHED)
        self.assertEqual(evaluate_search_palette(search | {"query": "absent"}).state, WorkbenchReleaseState.REVIEW)
        access = self.fixture.records[12].payload
        self.assertEqual(evaluate_accessibility(access).state, WorkbenchReleaseState.PASSED)
        self.assertEqual(evaluate_accessibility(access | {"surface": {"keyboard": True}}).state, WorkbenchReleaseState.REVIEW)

    def test_runtime_closes_49_stages(self) -> None:
        runtime = run_workbench_release_runtime(self.fixture, run_id="workbench-test")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 49)
        self.assertTrue(runtime.replay.deterministic)
        self.assertTrue(runtime.bundle.accepted)
        self.assertEqual(runtime.stage_ids[0], "data-audit")
        self.assertEqual(runtime.stage_ids[-1], "observability")


if __name__ == "__main__":
    unittest.main()
