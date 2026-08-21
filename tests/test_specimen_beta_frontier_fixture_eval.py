from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.specimen_beta_frontier_fixture_eval import (
    evaluate_specimen_beta_frontier_fixture,
)
from glio_noncode.specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")


class SpecimenBetaFrontierFixtureEvaluationTests(unittest.TestCase):
    def test_canonical_fixture_has_72_passing_checks(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_fixture(catalog)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 72)
        self.assertEqual(report.failed_check_ids, ())

    def test_positive_and_control_counts_are_separate(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_fixture(catalog)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertEqual(
            report.operation_ids,
            (
                "cancer_cell_fraction",
                "mosaicism",
                "origin",
                "subclone",
            ),
        )

    def test_origin_and_subclone_control_states_are_retained(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_fixture(catalog)
        by_id = {receipt.record_id: receipt for receipt in report.receipts}
        self.assertEqual(
            by_id["control-origin-conflicting-presence"].observed_result_state, "ambiguous"
        )
        self.assertEqual(
            by_id["control-origin-invalid-fraction"].observed_issue_codes,
            ("invalid_origin_fraction",),
        )
        self.assertEqual(by_id["control-subclone-boundary"].observed_result_state, "ambiguous")
        self.assertEqual(
            by_id["control-subclone-invalid-row"].observed_issue_codes, ("invalid_subclone_record",)
        )

    def test_ccf_zero_purity_is_abstained_at_item_level(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_fixture(catalog)
        receipt = next(
            item for item in report.receipts if item.record_id == "control-ccf-zero-purity"
        )
        self.assertEqual(receipt.observed_result_state, "partial")
        self.assertEqual(receipt.observed_counts["abstained"], 1)
        self.assertEqual(receipt.observed_counts["partial"], 0)

    def test_mosaicism_contamination_flag_is_counted(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_fixture(catalog)
        receipt = next(
            item for item in report.receipts if item.record_id == "control-mosaic-contamination"
        )
        self.assertEqual(receipt.observed_counts["contamination_flags"], 1)
        self.assertEqual(receipt.observed_result_state, "partial")

    def test_expected_state_mutation_fails_only_the_state_check(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_result_state"] = "partial"
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_beta_frontier_fixture(catalog)
        self.assertFalse(report.passed)
        self.assertIn("positive-origin-separated:result-state", report.failed_check_ids)

    def test_sanitized_outputs_do_not_include_raw_records(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_fixture(catalog)
        for receipt in report.receipts:
            self.assertTrue(receipt.output_address.startswith("sha256:"))
        serialized = json.dumps(report.to_dict())
        self.assertNotIn('"records"', serialized)

    def test_evaluation_is_deterministic(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        first = evaluate_specimen_beta_frontier_fixture(catalog)
        second = evaluate_specimen_beta_frontier_fixture(catalog)
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
