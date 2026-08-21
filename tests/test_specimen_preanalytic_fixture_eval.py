from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.specimen_preanalytic_fixture_eval import evaluate_specimen_preanalytic_fixture
from glio_noncode.specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog

FIXTURE = Path("examples/specimen-preanalytic-public-aggregate.json")


class SpecimenPreanalyticFixtureEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenPreanalyticFixtureCatalog.from_file(FIXTURE)

    def test_full_fixture_passes_with_deep_check_floor(self) -> None:
        report = evaluate_specimen_preanalytic_fixture(self.catalog)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, "accepted")
        self.assertEqual(len(report.receipts), 12)
        self.assertEqual(len(report.checks), 131)
        self.assertEqual(report.failed_check_ids, ())

    def test_operation_receipts_cover_all_four_operations(self) -> None:
        report = evaluate_specimen_preanalytic_fixture(self.catalog)
        self.assertEqual(
            set(report.operation_ids),
            {"preanalytic_quality", "assay_lineage", "identity_adjudication", "context_envelope"},
        )
        self.assertEqual(sum(item.role == "positive" for item in report.receipts), 4)
        self.assertEqual(sum(item.role == "control" for item in report.receipts), 8)

    def test_controls_retain_operation_issue_codes(self) -> None:
        report = evaluate_specimen_preanalytic_fixture(self.catalog)
        by_id = {item.record_id: item for item in report.receipts}
        self.assertIn(
            "preanalytic_threshold_failed", by_id["control-preanalytic-ischemia"].issue_codes
        )
        self.assertIn("missing_parent_node", by_id["control-assay-missing-parent"].issue_codes)
        self.assertIn("duplicate_lineage_node", by_id["control-assay-duplicate-node"].issue_codes)
        self.assertIn("identity_tie", by_id["control-identity-tie"].issue_codes)
        self.assertIn("identity_conflict", by_id["control-identity-conflict"].issue_codes)
        self.assertIn(
            "missing_identity_address", by_id["control-context-missing-identity"].issue_codes
        )
        self.assertIn("envelope_context_mismatch", by_id["control-context-drift"].issue_codes)

    def test_output_projection_does_not_copy_raw_payload(self) -> None:
        report = evaluate_specimen_preanalytic_fixture(self.catalog)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn('"payload"', serialized)
        self.assertNotIn('"records"', serialized)
        self.assertNotIn('"patient_id"', serialized)

    def test_evaluation_is_deterministic(self) -> None:
        first = evaluate_specimen_preanalytic_fixture(self.catalog)
        second = evaluate_specimen_preanalytic_fixture(self.catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            tuple(item.output_address for item in first.receipts),
            tuple(item.output_address for item in second.receipts),
        )

    def test_expected_state_mutation_is_reviewed(self) -> None:
        record = replace(
            self.catalog.records[0], expected_state=self.catalog.controls[0].expected_state
        )
        mutated = replace(self.catalog, records=(record,) + self.catalog.records[1:])
        report = evaluate_specimen_preanalytic_fixture(mutated)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("positive-results" in item.check_id for item in report.checks if not item.passed)
        )


if __name__ == "__main__":
    unittest.main()
