"""Operation execution tests for Domain 02 C13-C16."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.structural_frontier_fixture_eval import evaluate_structural_frontier_fixture
from glio_noncode.structural_frontier_public_data import (
    StructuralFrontierFixtureCatalog,
    StructuralFrontierFixtureState,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"


class StructuralFrontierFixtureEvalTests(unittest.TestCase):
    def test_canonical_fixture_passes_with_72_checks(self) -> None:
        report = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        self.assertEqual(report.state, StructuralFrontierFixtureState.ACCEPTED)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.receipts), 12)
        self.assertEqual(len(report.checks), 72)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_each_positive_exercises_one_frontier_operation(self) -> None:
        report = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        positives = [receipt for receipt in report.receipts if receipt.expected_state == StructuralFrontierFixtureState.ACCEPTED]
        self.assertEqual(len(positives), 4)
        self.assertEqual({receipt.operation.value for receipt in positives}, {
            "tandem_repeat",
            "compound_haplotype",
            "breakpoint_uncertainty",
            "structural_evidence_export",
        })
        by_id = {receipt.record_id: receipt for receipt in positives}
        self.assertEqual(by_id["positive-tandem-repeat"].counts["expanded"], 1)
        self.assertEqual(by_id["positive-compound-haplotype"].counts["compatible"], 1)
        self.assertEqual(by_id["positive-breakpoint-uncertainty"].counts["high_confidence"], 1)
        self.assertEqual(by_id["positive-structural-evidence-export"].counts["published"], 1)

    def test_controls_preserve_review_states_and_issue_reasons(self) -> None:
        report = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        controls = [receipt for receipt in report.receipts if receipt.expected_state == StructuralFrontierFixtureState.REVIEW]
        self.assertEqual(len(controls), 8)
        self.assertTrue(all(receipt.observed_state == StructuralFrontierFixtureState.REVIEW for receipt in controls))
        by_id = {receipt.record_id: receipt for receipt in controls}
        self.assertEqual(by_id["control-tandem-invalid-motif"].observed_result_state, "review")
        self.assertEqual(by_id["control-compound-incomplete"].observed_result_state, "review")
        self.assertEqual(by_id["control-breakpoint-low-confidence"].observed_result_state, "review")
        self.assertEqual(by_id["control-export-missing-field"].observed_result_state, "invalid")
        self.assertIn("invalid_motif", by_id["control-tandem-invalid-motif"].issue_codes)
        self.assertIn("incomplete_haplotype", by_id["control-compound-incomplete"].issue_codes)
        self.assertIn("inverted_left_interval", by_id["control-breakpoint-inverted"].issue_codes)
        self.assertIn("validation_error", by_id["control-export-context-drift"].issue_codes)

    def test_export_receipt_uses_published_result_state(self) -> None:
        report = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        receipt = next(item for item in report.receipts if item.operation.value == "structural_evidence_export" and item.expected_state == StructuralFrontierFixtureState.ACCEPTED)
        self.assertEqual(receipt.observed_result_state, "published")
        self.assertEqual(receipt.counts, {"evidence": 2, "sources": 2, "published": 1})

    def test_control_within_uncertainty_is_not_expanded(self) -> None:
        report = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        receipt = next(item for item in report.receipts if item.record_id == "control-tandem-within-uncertainty")
        self.assertEqual(receipt.observed_result_state, "accepted")
        self.assertEqual(receipt.counts["expanded"], 0)
        self.assertEqual(receipt.issue_codes, ())

    def test_missing_required_haplotype_variant_is_review(self) -> None:
        report = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        receipt = next(item for item in report.receipts if item.record_id == "control-compound-incomplete")
        self.assertEqual(receipt.counts["review"], 1)
        self.assertEqual(receipt.counts["compatible"], 0)
        self.assertIn("incomplete_haplotype", receipt.issue_codes)

    def test_invalid_export_does_not_copy_input_row(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["controls"][0]["payload"]["records"] = "not-an-array"
        report = evaluate_structural_frontier_fixture(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertIn("validation_error", report.receipts[4].issue_codes)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("not-an-array", serialized)

    def test_expected_count_drift_fails_only_declared_check(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["positives"][0]["expected_counts"]["expanded"] = 99
        report = evaluate_structural_frontier_fixture(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertEqual([check.check_id for check in report.checks if not check.passed], ["positive-tandem-repeat:count-expanded"])

    def test_required_issue_drift_fails_named_issue_check(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["controls"][0]["required_issue_codes"] = ["invented_issue"]
        report = evaluate_structural_frontier_fixture(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertIn("control-tandem-invalid-motif:issue-invented_issue", [check.check_id for check in report.checks if not check.passed])

    def test_evaluation_is_deterministic_and_sanitized(self) -> None:
        first = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        second = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())
        serialized = json.dumps(first.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("subject_id", serialized)

    def test_all_receipts_are_addressed_and_have_nonnegative_counts(self) -> None:
        report = evaluate_structural_frontier_fixture(FIXTURE.as_posix())
        for receipt in report.receipts:
            self.assertRegex(receipt.output_address, r"^sha256:[0-9a-f]{64}$")
            self.assertTrue(all(value >= 0 for value in receipt.counts.values()))
            self.assertTrue(receipt.detail)


if __name__ == "__main__":
    unittest.main()
