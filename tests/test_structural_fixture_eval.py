"""Execution and control-path tests for Domain 02 C01-C04."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_fixture_eval import evaluate_structural_fixture
from glio_noncode.structural_public_data import StructuralFixtureCatalog, StructuralFixtureState

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "structural-public-aggregate.json"


class StructuralFixtureEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_evaluation_passes_with_all_four_operations(self) -> None:
        report = evaluate_structural_fixture(str(FIXTURE_PATH))
        self.assertEqual(report.state, StructuralFixtureState.ACCEPTED)
        self.assertTrue(report.passed)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertEqual(len(report.receipts), 12)
        self.assertGreaterEqual(len(report.checks), 30)
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_positive_records_cover_expected_domain_states(self) -> None:
        report = evaluate_structural_fixture(str(FIXTURE_PATH))
        receipts = {item.record_id: item for item in report.receipts}
        self.assertEqual(receipts["positive-reconstruction"].observed_result_state, "eventful")
        self.assertEqual(receipts["positive-consensus"].observed_result_state, "supported")
        self.assertEqual(receipts["positive-complex"].observed_result_state, "ambiguous")
        self.assertEqual(receipts["positive-copy-number"].observed_result_state, "mixed")
        self.assertEqual(receipts["positive-reconstruction"].counts["events"], 3)
        self.assertEqual(receipts["positive-copy-number"].counts["ambiguous_segments"], 1)

    def test_controls_keep_required_issue_codes_and_review_state(self) -> None:
        report = evaluate_structural_fixture(str(FIXTURE_PATH))
        controls = [item for item in report.receipts if item.record_id.startswith("control-")]
        self.assertEqual(len(controls), 8)
        self.assertTrue(all(item.observed_state == StructuralFixtureState.REVIEW for item in controls))
        required = {
            "control-reconstruction-missing-mate": "missing_mate_id",
            "control-reconstruction-nonreciprocal": "non_reciprocal_mate",
            "control-consensus-malformed-row": "invalid_sv_caller_row",
            "control-complex-no-breakpoint": "event_without_breakpoints",
            "control-complex-invalid-event": "validation_error",
            "control-copy-number-invalid-start": "validation_error",
            "control-copy-number-negative-value": "validation_error",
        }
        for record_id, issue_code in required.items():
            self.assertIn(issue_code, next(item for item in controls if item.record_id == record_id).issue_codes)

    def test_consensus_disagreement_is_review_without_an_exception(self) -> None:
        report = evaluate_structural_fixture(str(FIXTURE_PATH))
        receipt = next(item for item in report.receipts if item.record_id == "control-consensus-disagreement")
        self.assertEqual(receipt.observed_state, StructuralFixtureState.REVIEW)
        self.assertEqual(receipt.observed_result_state, "ambiguous")
        self.assertEqual(receipt.issue_codes, ())

    def test_reconstruction_keeps_phased_path_and_no_false_warning(self) -> None:
        report = evaluate_structural_fixture(str(FIXTURE_PATH))
        receipt = next(item for item in report.receipts if item.record_id == "positive-reconstruction")
        self.assertEqual(receipt.issue_codes, ())
        self.assertEqual(receipt.counts["events"], 3)
        output = next(
            check for check in report.checks if check.check_id == "positive-reconstruction:state"
        )
        self.assertTrue(output.passed)

    def test_result_addresses_are_unique_across_fixture_records(self) -> None:
        report = evaluate_structural_fixture(str(FIXTURE_PATH))
        addresses = [item.output_address for item in report.receipts]
        self.assertEqual(len(addresses), len(set(addresses)))

    def test_missing_expected_count_fails_the_fixture_assertion(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["positives"][0]["expected_counts"]["events"] = 99
        report = evaluate_structural_fixture(StructuralFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        failed = next(
            check for check in report.checks if check.check_id == "positive-reconstruction:count:events"
        )
        self.assertFalse(failed.passed)
        self.assertEqual(failed.expected, 99)

    def test_expected_result_state_drift_is_visible(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["positives"][1]["expected_result_state"] = "ambiguous"
        report = evaluate_structural_fixture(StructuralFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        failed = next(
            check for check in report.checks if check.check_id == "positive-consensus:result-state"
        )
        self.assertFalse(failed.passed)

    def test_control_without_required_issue_code_fails(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["controls"][0]["required_issue_codes"] = ["different-code"]
        report = evaluate_structural_fixture(StructuralFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        failed = next(
            check for check in report.checks if check.check_id == "control-reconstruction-missing-mate:issues"
        )
        self.assertFalse(failed.passed)

    def test_repeated_evaluation_is_deterministic(self) -> None:
        first = evaluate_structural_fixture(str(FIXTURE_PATH))
        second = evaluate_structural_fixture(str(FIXTURE_PATH))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_output_does_not_copy_restricted_marker(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["positives"][0]["payload"]["raw_private_payload_marker"] = "must-not-publish"
        report = evaluate_structural_fixture(StructuralFixtureCatalog.from_mapping(raw))
        self.assertNotIn("must-not-publish", json.dumps(report.to_dict()))


if __name__ == "__main__":
    unittest.main()
