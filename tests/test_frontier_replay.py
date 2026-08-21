from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_replay import (
    FrontierReplayRunner,
    ReplayExpectation,
    replay_frontier_fixtures,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "frontier-glioma-case.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCES = ("glioma-regulatory-reference", "regulatory-assay-contract-reference")


class FrontierReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = FrontierReplayRunner()

    def alternate_context_fixture(self) -> dict[str, object]:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["fixture_id"] = "glioma-frontier-public-aggregate-002"
        fixture["context"]["cell_state"] = "malignant_astrocyte_like"
        alternate = CONTEXT.replace("malignant_oligodendrocyte_like", "malignant_astrocyte_like")
        return json.loads(json.dumps(fixture).replace(CONTEXT, alternate))

    def test_single_fixture_replay_passes_declared_expectation(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=ReplayExpectation(
                fixture_id="glioma-frontier-public-aggregate-001",
                context_key=CONTEXT,
                source_ids=SOURCES,
            ),
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.observed_state, "accepted")
        self.assertEqual(receipt.check_count, 49)
        self.assertEqual(receipt.context_key, CONTEXT)
        self.assertEqual(receipt.source_ids, SOURCES)
        self.assertRegex(receipt.content_address or "", r"^sha256:[0-9a-f]{64}$")

    def test_replay_report_passes_one_case(self) -> None:
        report = self.runner.replay([FIXTURE], required_context_key=CONTEXT)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, FrontierState.ACCEPTED)
        self.assertEqual(report.case_receipts[0].fixture_id, "glioma-frontier-public-aggregate-001")
        self.assertEqual(report.context_keys, (CONTEXT,))
        self.assertEqual(report.source_ids, SOURCES)
        self.assertEqual(report.failed_fixture_ids, ())

    def test_convenience_function_matches_runner(self) -> None:
        expected = self.runner.replay([FIXTURE]).to_dict()
        actual = replay_frontier_fixtures([FIXTURE]).to_dict()
        self.assertEqual(actual, expected)

    def test_replay_requires_at_least_one_path(self) -> None:
        with self.assertRaises(ValidationError):
            self.runner.replay([])

    def test_expectation_rejects_zero_minimum_checks(self) -> None:
        with self.assertRaises(ValidationError):
            ReplayExpectation(minimum_checks=0)

    def test_expectation_rejects_empty_fixture_id(self) -> None:
        with self.assertRaises(ValidationError):
            ReplayExpectation(fixture_id=" ")

    def test_fixture_id_mismatch_fails_case_receipt(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=ReplayExpectation(fixture_id="different-fixture"),
        )
        self.assertFalse(receipt.passed)
        self.assertIn("fixture_id_mismatch", receipt.error or "")

    def test_context_mismatch_fails_case_receipt(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=ReplayExpectation(context_key="GRCh38|other|adult|state|core|untreated"),
        )
        self.assertFalse(receipt.passed)
        self.assertIn("context_key_mismatch", receipt.error or "")

    def test_source_set_mismatch_fails_case_receipt(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=ReplayExpectation(source_ids=("wrong-source",)),
        )
        self.assertFalse(receipt.passed)
        self.assertIn("source_set_mismatch", receipt.error or "")

    def test_minimum_check_mismatch_fails_case_receipt(self) -> None:
        receipt = self.runner.replay_file(FIXTURE, expectation=ReplayExpectation(minimum_checks=50))
        self.assertFalse(receipt.passed)
        self.assertIn("insufficient_checks", receipt.error or "")

    def test_duplicate_fixture_identity_is_reviewed(self) -> None:
        report = self.runner.replay([FIXTURE, FIXTURE])
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertEqual(report.duplicate_fixture_ids, ("glioma-frontier-public-aggregate-001",))
        self.assertIn(
            "duplicate_fixture_id:glioma-frontier-public-aggregate-001",
            report.integrity_issues,
        )

    def test_required_context_missing_is_reviewed(self) -> None:
        report = self.runner.replay([FIXTURE], required_context_key="other")
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("required_context_missing", report.integrity_issues)

    def test_invalid_fixture_is_retained_as_failed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            report = self.runner.replay([path])
            self.assertEqual(report.state, FrontierState.REVIEW)
            self.assertEqual(report.case_receipts[0].observed_state, "error")
            self.assertIn("frontier fixture must be an object", report.case_receipts[0].error or "")

    def test_missing_path_is_retained_as_failed_receipt(self) -> None:
        path = ROOT / "examples" / "missing-frontier-case.json"
        report = self.runner.replay([path])
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertEqual(report.case_receipts[0].observed_state, "error")
        self.assertIn("missing-frontier-case.json", report.case_receipts[0].error or "")

    def test_failed_fixture_is_reported_in_batch(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["pipelines"]["workbench"]["accessibility_surface"]["contrast"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            report = self.runner.replay([path])
            self.assertEqual(report.state, FrontierState.REVIEW)
            self.assertEqual(report.failed_fixture_ids, ("glioma-frontier-public-aggregate-001",))
            self.assertIn(
                "failed_fixture:glioma-frontier-public-aggregate-001",
                report.integrity_issues,
            )

    def test_mixed_context_batch_is_reviewed(self) -> None:
        fixture = self.alternate_context_fixture()
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            second.write_text(json.dumps(fixture), encoding="utf-8")
            report = self.runner.replay([first, second])
            self.assertEqual(report.state, FrontierState.REVIEW)
            self.assertIn("mixed_context_keys", report.integrity_issues)
            self.assertEqual(len(report.context_keys), 2)

    def test_mixed_context_can_be_explicitly_allowed(self) -> None:
        fixture = self.alternate_context_fixture()
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            second.write_text(json.dumps(fixture), encoding="utf-8")
            report = self.runner.replay([first, second], require_same_context=False)
            self.assertTrue(report.passed)
            self.assertEqual(report.state, FrontierState.ACCEPTED)

    def test_replay_report_is_deterministic(self) -> None:
        first = self.runner.replay([FIXTURE]).to_dict()
        second = self.runner.replay([FIXTURE]).to_dict()
        self.assertEqual(first, second)

    def test_report_contains_stable_content_address(self) -> None:
        report = self.runner.replay([FIXTURE])
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_case_receipt_serializes_error_as_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{bad", encoding="utf-8")
            receipt = self.runner.replay_file(path)
            payload = receipt.to_dict()
            self.assertEqual(payload["observed_state"], "error")
            self.assertIsInstance(payload["error"], str)

    def test_expectations_are_selected_by_string_path(self) -> None:
        expectation = ReplayExpectation(fixture_id="wrong")
        report = self.runner.replay([FIXTURE], expectations={str(FIXTURE): expectation})
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("fixture_id_mismatch", report.case_receipts[0].error or "")

    def test_deepcopy_does_not_change_replay_output(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text(json.dumps(fixture), encoding="utf-8")
            second.write_text(json.dumps(copy.deepcopy(fixture)), encoding="utf-8")
            first_report = self.runner.replay([first]).to_dict()
            second_report = self.runner.replay([second]).to_dict()
            self.assertEqual(
                first_report["case_receipts"][0]["content_address"],
                second_report["case_receipts"][0]["content_address"],
            )


if __name__ == "__main__":
    unittest.main()
