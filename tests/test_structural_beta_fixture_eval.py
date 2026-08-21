"""Fixture execution tests for Domain 02 C05-C08."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_beta_fixture_eval import evaluate_structural_beta_fixture
from glio_noncode.structural_beta_public_data import (
    StructuralBetaFixtureCatalog,
    StructuralBetaFixtureState,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"


class StructuralBetaFixtureEvalTests(unittest.TestCase):
    def test_fixture_evaluation_passes_with_substantial_checks(self) -> None:
        report = evaluate_structural_beta_fixture(str(FIXTURE))
        self.assertEqual(report.state, StructuralBetaFixtureState.ACCEPTED)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.receipts), 12)
        self.assertEqual(len(report.checks), 63)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_each_positive_exercises_one_operation(self) -> None:
        report = evaluate_structural_beta_fixture(str(FIXTURE))
        positives = {receipt.record_id: receipt for receipt in report.receipts if receipt.expected_state.value == "accepted"}
        self.assertEqual(len(positives), 4)
        self.assertEqual(
            {receipt.operation.value for receipt in positives.values()},
            {"focal_amplification", "chromothripsis", "ecdna", "enhancer_hijacking"},
        )
        self.assertEqual(positives["positive-enhancer-hijacking"].observed_result_state, "ambiguous")

    def test_controls_keep_review_state_and_expected_detector_result(self) -> None:
        report = evaluate_structural_beta_fixture(str(FIXTURE))
        controls = {receipt.record_id: receipt for receipt in report.receipts if receipt.expected_state.value == "review"}
        self.assertEqual(len(controls), 8)
        self.assertTrue(all(receipt.observed_state == StructuralBetaFixtureState.REVIEW for receipt in controls.values()))
        self.assertEqual(controls["control-focal-no-amplification"].observed_result_state, "abstained")
        self.assertEqual(controls["control-chromothripsis-far-gaps"].observed_result_state, "abstained")
        self.assertEqual(controls["control-ecdna-conflicting-linear"].observed_result_state, "ambiguous")
        self.assertEqual(controls["control-enhancer-context-mismatch"].observed_result_state, "out_of_domain")

    def test_issue_codes_are_required_only_where_declared(self) -> None:
        report = evaluate_structural_beta_fixture(str(FIXTURE))
        by_id = {receipt.record_id: receipt for receipt in report.receipts}
        self.assertIn("invalid_copy_number_record", by_id["control-focal-negative-copy"].issue_codes)
        self.assertIn("missing_structural_bridge", by_id["control-enhancer-missing-bridge"].issue_codes)
        self.assertIn("context_mismatch", by_id["control-enhancer-context-mismatch"].issue_codes)
        self.assertEqual(by_id["positive-ecdna"].issue_codes, ())

    def test_expected_count_drift_fails_one_record_and_report(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["expected_counts"]["candidates"] = 99
        report = evaluate_structural_beta_fixture(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        failed = [check for check in report.checks if not check.passed]
        self.assertEqual([check.check_id for check in failed], ["positive-focal-amplification:count-candidates"])

    def test_missing_required_issue_fails_control(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["controls"][6]["required_issue_codes"] = ["made_up_issue"]
        report = evaluate_structural_beta_fixture(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id.endswith("issue-made_up_issue")).passed)

    def test_positive_abstention_cannot_pass_as_accepted(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["payload"]["records"][0]["copy_number"] = 3
        raw["positives"][0]["payload"]["records"][1]["copy_number"] = 3
        report = evaluate_structural_beta_fixture(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertEqual(report.receipts[0].observed_result_state, "abstained")

    def test_evaluation_is_deterministic(self) -> None:
        first = evaluate_structural_beta_fixture(str(FIXTURE))
        second = evaluate_structural_beta_fixture(str(FIXTURE))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_receipts_are_addressed_and_do_not_copy_raw_payload(self) -> None:
        report = evaluate_structural_beta_fixture(str(FIXTURE))
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertTrue(all(receipt.output_address.startswith("sha256:") for receipt in report.receipts))
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn('"copy_number": -1', serialized)

    def test_counts_are_non_negative_and_complete(self) -> None:
        report = evaluate_structural_beta_fixture(str(FIXTURE))
        for receipt in report.receipts:
            self.assertTrue(all(value >= 0 for value in receipt.counts.values()))
            self.assertIn("candidates", receipt.counts)
            self.assertIn("issues", receipt.counts)


if __name__ == "__main__":
    unittest.main()
