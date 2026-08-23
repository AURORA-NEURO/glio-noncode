from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.control_frontier_contracts import ControlFrontierOperation, ControlFrontierRole, ControlFrontierState
from glio_noncode.control_frontier_delta import compare_control_frontier_evaluations
from glio_noncode.control_frontier_fixture_eval import evaluate_control_frontier_fixture
from glio_noncode.control_frontier_invariants import assert_control_frontier_invariants, evaluate_control_frontier_invariants
from glio_noncode.control_frontier_partition import build_control_frontier_partitions
from glio_noncode.control_frontier_public_data import default_control_frontier_fixture
from glio_noncode.control_frontier_query import ControlFrontierQuery, query_control_frontier_evaluation
from glio_noncode.control_frontier_release_checks import evaluate_control_frontier_release_checks
from glio_noncode.control_frontier_runtime import run_control_frontier_runtime
from glio_noncode.control_frontier_transcript import build_control_frontier_transcript, verify_control_frontier_transcript
from glio_noncode.control_frontier_versioning import inspect_control_frontier_version, migrate_control_frontier_metadata
from glio_noncode.serialization import jsonable


class ControlFrontierSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_control_frontier_fixture()
        cls.evaluation = evaluate_control_frontier_fixture(cls.fixture)

    def test_invariants_close_fixture_and_evaluation(self) -> None:
        report = evaluate_control_frontier_invariants(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.invariants), 10)
        self.assertTrue(assert_control_frontier_invariants(self.fixture, self.evaluation).accepted)

    def test_query_can_select_controls_by_operation_and_issue(self) -> None:
        query = ControlFrontierQuery(
            operation=ControlFrontierOperation.POLICY_CLAIM_GATE,
            role=ControlFrontierRole.CONTROL,
            issue_code="sensitive_input",
        )
        result = query_control_frontier_evaluation(self.evaluation, query)
        self.assertTrue(result.accepted)
        self.assertEqual(result.total_matches, 1)
        self.assertEqual(result.hits[0].record_id, "C05-CTRL-001")

    def test_query_can_select_states(self) -> None:
        result = query_control_frontier_evaluation(
            self.evaluation,
            ControlFrontierQuery(states=(ControlFrontierState.OUT_OF_DOMAIN,)),
        )
        self.assertEqual({item.record_id for item in result.hits}, {"C09-CTRL-003", "C10-CTRL-001", "C11-CTRL-001", "C12-CTRL-003"})

    def test_partitions_cover_all_operations_and_roles(self) -> None:
        report = build_control_frontier_partitions(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.partition_count, 16)
        self.assertEqual(sum(len(item.record_ids) for item in report.partitions), 32)
        positives = [item for item in report.partitions if item.role is ControlFrontierRole.POSITIVE]
        self.assertEqual(sum(item.accepted_count for item in positives), 8)

    def test_identical_evaluations_have_no_delta(self) -> None:
        report = compare_control_frontier_evaluations(self.evaluation, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.changed_count, 0)
        self.assertEqual(report.added_count, 0)
        self.assertEqual(report.removed_count, 0)

    def test_delta_detects_changed_acceptance(self) -> None:
        changed_execution = replace(self.evaluation.executions[0], accepted=False)
        changed_evaluation = replace(self.evaluation, executions=(changed_execution,) + self.evaluation.executions[1:])
        report = compare_control_frontier_evaluations(self.evaluation, changed_evaluation)
        self.assertEqual(report.changed_count, 1)
        self.assertEqual(next(item for item in report.rows if item.changed).record_id, "C05-POS-001")

    def test_transcript_is_contiguous_and_addressed(self) -> None:
        runtime = run_control_frontier_runtime(self.fixture, run_id="support-test")
        transcript = build_control_frontier_transcript(runtime)
        self.assertTrue(transcript.accepted)
        self.assertEqual(transcript.stage_count, 24)
        self.assertEqual(verify_control_frontier_transcript(transcript), ())

    def test_release_checks_close_runtime(self) -> None:
        runtime = run_control_frontier_runtime(self.fixture, run_id="release-check-test")
        report = evaluate_control_frontier_release_checks(runtime)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 10)

    def test_version_receipt_accepts_current_fixture(self) -> None:
        receipt = inspect_control_frontier_version(jsonable(self.fixture))
        self.assertTrue(receipt.compatible)
        self.assertEqual(receipt.migration_path, ())
        migrated = migrate_control_frontier_metadata({"fixture_id": self.fixture.fixture_id, "fixture_version": "old.v0", "records": []})
        self.assertNotEqual(migrated["fixture_version"], "old.v0")
        self.assertTrue(migrated["migration_receipt"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
