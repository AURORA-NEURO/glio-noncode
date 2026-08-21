from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.variation_public_data import VariationDataState
from glio_noncode.variation_replay import (
    VariationReplayExpectation,
    VariationReplayRunner,
    replay_variation_fixtures,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "variation-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCES = ("ncbi-clinvar-rs121913502", "ncbi-grch38-reference-assembly")


class VariationReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = VariationReplayRunner()

    def test_single_fixture_replay_passes_exact_expectation(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=VariationReplayExpectation(
                fixture_id="variation-public-aggregate-001",
                context_key=CONTEXT,
                source_ids=SOURCES,
            ),
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.observed_state, "accepted")
        self.assertEqual(receipt.check_count, 29)
        self.assertEqual(receipt.context_key, CONTEXT)
        self.assertEqual(receipt.source_ids, SOURCES)
        self.assertRegex(receipt.content_address or "", r"^sha256:[0-9a-f]{64}$")

    def test_batch_replay_passes_required_context(self) -> None:
        report = self.runner.replay([FIXTURE], required_context_key=CONTEXT)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, VariationDataState.ACCEPTED)
        self.assertEqual(report.context_keys, (CONTEXT,))
        self.assertEqual(report.source_ids, SOURCES)
        self.assertEqual(report.failed_fixture_ids, ())

    def test_convenience_function_matches_runner(self) -> None:
        expected = self.runner.replay([FIXTURE]).to_dict()
        actual = replay_variation_fixtures([FIXTURE]).to_dict()
        self.assertEqual(actual, expected)

    def test_replay_requires_at_least_one_path(self) -> None:
        with self.assertRaises(ValidationError):
            self.runner.replay([])

    def test_expectation_rejects_invalid_state(self) -> None:
        with self.assertRaises(ValidationError):
            VariationReplayExpectation(expected_state="unsupported")

    def test_expectation_rejects_zero_floor(self) -> None:
        with self.assertRaises(ValidationError):
            VariationReplayExpectation(minimum_checks=0)

    def test_fixture_id_mismatch_is_retained_in_receipt(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=VariationReplayExpectation(fixture_id="other-fixture"),
        )
        self.assertFalse(receipt.passed)
        self.assertIn("fixture_id_mismatch", receipt.error or "")

    def test_context_mismatch_is_retained_in_receipt(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=VariationReplayExpectation(context_key="other-context"),
        )
        self.assertFalse(receipt.passed)
        self.assertIn("context_key_mismatch", receipt.error or "")

    def test_source_set_mismatch_is_retained_in_receipt(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=VariationReplayExpectation(source_ids=("wrong-source",)),
        )
        self.assertFalse(receipt.passed)
        self.assertIn("source_set_mismatch", receipt.error or "")

    def test_check_floor_mismatch_is_retained_in_receipt(self) -> None:
        receipt = self.runner.replay_file(
            FIXTURE,
            expectation=VariationReplayExpectation(minimum_checks=30),
        )
        self.assertFalse(receipt.passed)
        self.assertIn("insufficient_checks", receipt.error or "")

    def test_duplicate_fixture_identity_is_reviewed(self) -> None:
        report = self.runner.replay([FIXTURE, FIXTURE])
        self.assertFalse(report.passed)
        self.assertEqual(report.state, VariationDataState.REVIEW)
        self.assertEqual(report.duplicate_fixture_ids, ("variation-public-aggregate-001",))
        self.assertIn(
            "duplicate_fixture_id:variation-public-aggregate-001",
            report.integrity_issues,
        )

    def test_required_context_missing_is_reviewed(self) -> None:
        report = self.runner.replay([FIXTURE], required_context_key="other-context")
        self.assertFalse(report.passed)
        self.assertIn("required_context_missing", report.integrity_issues)

    def test_invalid_fixture_is_retained_as_failed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            report = self.runner.replay([path])
        self.assertEqual(report.state, VariationDataState.REVIEW)
        self.assertEqual(report.case_receipts[0].observed_state, "error")
        self.assertIn("variation fixture must be an object", report.case_receipts[0].error or "")

    def test_missing_path_is_retained_as_failed_receipt(self) -> None:
        path = ROOT / "examples" / "missing-variation-fixture.json"
        report = self.runner.replay([path])
        self.assertEqual(report.state, VariationDataState.REVIEW)
        self.assertEqual(report.case_receipts[0].observed_state, "error")
        self.assertIn("missing-variation-fixture.json", report.case_receipts[0].error or "")

    def test_failed_fixture_is_reported_in_batch(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["records"][0]["payload"]["alternate"] = "<DEL>"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            report = self.runner.replay([path])
        self.assertEqual(report.state, VariationDataState.REVIEW)
        self.assertEqual(report.failed_fixture_ids, ("variation-public-aggregate-001",))
        self.assertIn(
            "failed_fixture:variation-public-aggregate-001",
            report.integrity_issues,
        )

    def test_replay_report_is_deterministic(self) -> None:
        first = self.runner.replay([FIXTURE]).to_dict()
        second = self.runner.replay([FIXTURE]).to_dict()
        self.assertEqual(first, second)
        self.assertRegex(first["content_address"], r"^sha256:[0-9a-f]{64}$")

    def test_mixed_context_batch_is_reviewed(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["fixture_id"] = "variation-public-aggregate-002"
        fixture["context"]["cell_state"] = "different_state"
        alternate_key = CONTEXT.replace("malignant_oligodendrocyte_like", "different_state")
        fixture["source_receipts"][0]["context_key"] = alternate_key
        fixture["source_receipts"][1]["context_key"] = alternate_key
        for record in fixture["records"]:
            record["context_key"] = alternate_key
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            second.write_text(json.dumps(fixture), encoding="utf-8")
            report = self.runner.replay([first, second])
        self.assertFalse(report.passed)
        self.assertIn("mixed_context_keys", report.integrity_issues)
        self.assertEqual(len(report.context_keys), 2)

    def test_mixed_context_can_be_explicitly_allowed(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["fixture_id"] = "variation-public-aggregate-002"
        fixture["context"]["cell_state"] = "different_state"
        alternate_key = CONTEXT.replace("malignant_oligodendrocyte_like", "different_state")
        for source in fixture["source_receipts"]:
            source["context_key"] = alternate_key
        for record in fixture["records"]:
            record["context_key"] = alternate_key
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            second.write_text(json.dumps(fixture), encoding="utf-8")
            report = self.runner.replay([first, second], require_same_context=False)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, VariationDataState.ACCEPTED)

    def test_expectations_can_be_selected_by_string_path(self) -> None:
        expectation = VariationReplayExpectation(fixture_id="wrong")
        report = self.runner.replay([FIXTURE], expectations={str(FIXTURE): expectation})
        self.assertFalse(report.passed)
        self.assertIn("fixture_id_mismatch", report.case_receipts[0].error or "")

    def test_case_receipt_serializes_errors_as_strings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{bad", encoding="utf-8")
            receipt = self.runner.replay_file(path)
        self.assertEqual(receipt.observed_state, "error")
        self.assertIsInstance(receipt.to_dict()["error"], str)


if __name__ == "__main__":
    unittest.main()
