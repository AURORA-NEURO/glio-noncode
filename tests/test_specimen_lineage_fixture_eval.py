from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.specimen_lineage_fixture_eval import (
    SpecimenLineageFixtureEvaluator,
    evaluate_specimen_lineage_fixture,
)
from glio_noncode.specimen_lineage_public_data import SpecimenLineageFixtureCatalog

FIXTURE = Path("examples/specimen-lineage-public-aggregate.json")


class SpecimenLineageFixtureEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)

    def test_full_fixture_passes_with_twelve_receipts(self) -> None:
        report = evaluate_specimen_lineage_fixture(self.catalog)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.receipts), 12)
        self.assertEqual(len(report.checks), 159)
        self.assertEqual(report.failed_check_ids, ())

    def test_all_four_operation_receipts_are_present(self) -> None:
        report = evaluate_specimen_lineage_fixture(self.catalog)
        self.assertEqual(
            {receipt.operation.value for receipt in report.receipts},
            {"region_lineage", "longitudinal_linking", "phase_mapping", "treatment_context"},
        )
        self.assertEqual(len({receipt.record_id for receipt in report.receipts}), 12)

    def test_expected_control_states_are_retained(self) -> None:
        report = evaluate_specimen_lineage_fixture(self.catalog)
        controls = {
            receipt.record_id: receipt
            for receipt in report.receipts
            if receipt.fixture_state.value == "review"
        }
        self.assertEqual(controls["control-region-cycle"].observed_result_state, "contradictory")
        self.assertEqual(controls["control-treatment-overlap"].observed_result_state, "ambiguous")
        self.assertEqual(controls["control-phase-later-only"].observed_result_state, "partial")

    def test_operation_counts_match_fixture_contracts(self) -> None:
        report = evaluate_specimen_lineage_fixture(self.catalog)
        receipts = {receipt.record_id: receipt for receipt in report.receipts}
        self.assertEqual(receipts["positive-region-branching"].observed_counts["edges"], 2)
        self.assertEqual(
            receipts["positive-longitudinal-chain"].observed_counts["supported_links"], 2
        )
        self.assertEqual(receipts["positive-phase-explicit"].observed_counts["recurrence"], 1)
        self.assertEqual(receipts["positive-treatment-window"].observed_counts["on_treatment"], 1)

    def test_output_projection_has_no_raw_record_collection(self) -> None:
        report = SpecimenLineageFixtureEvaluator().evaluate(self.catalog)
        for receipt in report.receipts:
            self.assertTrue(
                all(
                    check.passed
                    for check in receipt.checks
                    if check.check_id.endswith("sanitized-output")
                )
            )
            self.assertTrue(receipt.output_address.startswith("sha256:"))

    def test_evaluation_is_deterministic(self) -> None:
        first = evaluate_specimen_lineage_fixture(self.catalog)
        second = evaluate_specimen_lineage_fixture(self.catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            [receipt.output_address for receipt in first.receipts],
            [receipt.output_address for receipt in second.receipts],
        )

    def test_fixture_evaluator_exposes_operation_dispatch(self) -> None:
        evaluator = SpecimenLineageFixtureEvaluator()
        self.assertTrue(callable(evaluator.evaluate))
        self.assertTrue(callable(evaluator._execute))


if __name__ == "__main__":
    unittest.main()
