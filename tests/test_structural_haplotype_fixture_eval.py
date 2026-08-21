"""Fixture execution tests for Domain 02 C09-C12."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_haplotype_fixture_eval import evaluate_structural_haplotype_fixture
from glio_noncode.structural_haplotype_public_data import (
    StructuralHaplotypeFixtureCatalog,
    StructuralHaplotypeFixtureState,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-haplotype-public-aggregate.json"


class StructuralHaplotypeFixtureEvalTests(unittest.TestCase):
    def test_fixture_evaluation_passes_with_substantial_checks(self) -> None:
        report = evaluate_structural_haplotype_fixture(str(FIXTURE))
        self.assertEqual(report.state, StructuralHaplotypeFixtureState.ACCEPTED)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.receipts), 12)
        self.assertEqual(len(report.checks), 72)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_each_positive_exercises_one_operation(self) -> None:
        report = evaluate_structural_haplotype_fixture(str(FIXTURE))
        positives = {receipt.record_id: receipt for receipt in report.receipts if receipt.expected_state == StructuralHaplotypeFixtureState.ACCEPTED}
        self.assertEqual(len(positives), 4)
        self.assertEqual(
            {receipt.operation.value for receipt in positives.values()},
            {"phased_haplotype", "allele_aware_sv", "pangenome_projection", "repeat_mobile_annotation"},
        )
        self.assertEqual(positives["positive-phased-haplotype"].observed_result_state, "supported")
        self.assertEqual(positives["positive-allele-aware-sv"].counts["events"], 1)
        self.assertEqual(positives["positive-pangenome-projection"].counts["matches"], 1)
        self.assertEqual(positives["positive-repeat-mobile-annotation"].counts["hits"], 1)

    def test_controls_keep_review_fixture_state_and_expected_result(self) -> None:
        report = evaluate_structural_haplotype_fixture(str(FIXTURE))
        controls = {receipt.record_id: receipt for receipt in report.receipts if receipt.expected_state == StructuralHaplotypeFixtureState.REVIEW}
        self.assertEqual(len(controls), 8)
        self.assertTrue(all(receipt.observed_state == StructuralHaplotypeFixtureState.REVIEW for receipt in controls.values()))
        self.assertEqual(controls["control-phased-unphased"].observed_result_state, "ambiguous")
        self.assertEqual(controls["control-phased-context-drift"].observed_result_state, "out_of_domain")
        self.assertEqual(controls["control-allele-conflict"].observed_result_state, "contradictory")
        self.assertEqual(controls["control-pangenome-ambiguous-paths"].observed_result_state, "ambiguous")
        self.assertEqual(controls["control-repeat-context-drift"].observed_result_state, "partial")

    def test_required_issue_codes_remain_visible(self) -> None:
        report = evaluate_structural_haplotype_fixture(str(FIXTURE))
        by_id = {receipt.record_id: receipt for receipt in report.receipts}
        self.assertIn("context_mismatch", by_id["control-phased-context-drift"].issue_codes)
        self.assertIn("conflicting_allele_observation", by_id["control-allele-conflict"].issue_codes)
        self.assertIn("annotation_context_mismatch", by_id["control-repeat-context-drift"].issue_codes)
        self.assertEqual(by_id["positive-pangenome-projection"].issue_codes, ())

    def test_expected_count_drift_fails_one_record_and_report(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["expected_counts"]["haplotypes"] = 99
        report = evaluate_structural_haplotype_fixture(StructuralHaplotypeFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        failed = [check.check_id for check in report.checks if not check.passed]
        self.assertEqual(failed, ["positive-phased-haplotype:count-haplotypes"])

    def test_missing_required_issue_fails_control(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["controls"][1]["required_issue_codes"] = ["invented_issue"]
        report = evaluate_structural_haplotype_fixture(StructuralHaplotypeFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id.endswith("issue-invented_issue")).passed)

    def test_positive_phasing_with_unphased_input_cannot_pass_as_supported(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["payload"]["records"][0]["GT"] = "0/1"
        raw["positives"][0]["expected_result_state"] = "supported"
        report = evaluate_structural_haplotype_fixture(StructuralHaplotypeFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertEqual(report.receipts[0].observed_result_state, "partial")

    def test_invalid_records_array_fails_without_copying_payload(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["payload"]["records"] = "not-an-array"
        report = evaluate_structural_haplotype_fixture(StructuralHaplotypeFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertIn("validation_error", report.receipts[0].issue_codes)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("not-an-array", serialized)

    def test_evaluation_is_deterministic(self) -> None:
        first = evaluate_structural_haplotype_fixture(str(FIXTURE))
        second = evaluate_structural_haplotype_fixture(str(FIXTURE))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_receipts_are_addressed_and_sanitized(self) -> None:
        report = evaluate_structural_haplotype_fixture(str(FIXTURE))
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertTrue(all(receipt.output_address.startswith("sha256:") for receipt in report.receipts))
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("AGCT", serialized)

    def test_counts_are_non_negative_and_operation_specific(self) -> None:
        report = evaluate_structural_haplotype_fixture(str(FIXTURE))
        for receipt in report.receipts:
            self.assertTrue(all(value >= 0 for value in receipt.counts.values()))
            self.assertIn("issues", receipt.counts)
            if receipt.operation.value in {"phased_haplotype", "allele_aware_sv"}:
                self.assertTrue(any(key in receipt.counts for key in ("haplotypes", "events")))
            else:
                self.assertTrue(any(key in receipt.counts for key in ("matches", "hits")))


if __name__ == "__main__":
    unittest.main()
