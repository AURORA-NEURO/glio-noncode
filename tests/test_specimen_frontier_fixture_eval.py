"""Operation execution tests for Domain 03 C01-C04."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.specimen_frontier_fixture_eval import evaluate_specimen_frontier_fixture
from glio_noncode.specimen_frontier_public_data import SpecimenFrontierFixtureCatalog

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"


class SpecimenFrontierFixtureEvalTests(unittest.TestCase):
    def test_canonical_evaluation_passes_72_checks_and_twelve_receipts(self) -> None:
        report = evaluate_specimen_frontier_fixture(str(FIXTURE))
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 72)
        self.assertEqual(len(report.receipts), 12)
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_positive_operation_states_and_counts_are_explicit(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_frontier_fixture(catalog)
        receipts = {receipt.record_id: receipt for receipt in report.receipts}
        self.assertEqual(receipts["positive-ontology-mapping"].observed_result_state, "supported")
        self.assertEqual(receipts["positive-matched-normal"].counts["supported"], 1)
        self.assertEqual(receipts["positive-purity-ploidy"].counts["records"], 2)
        self.assertEqual(receipts["positive-sample-integrity"].observed_result_state, "clear")

    def test_review_controls_preserve_specific_issue_codes(self) -> None:
        report = evaluate_specimen_frontier_fixture(str(FIXTURE))
        receipts = {receipt.record_id: receipt for receipt in report.receipts}
        self.assertEqual(
            receipts["control-ontology-conflicting-subject"].issue_codes,
            ("ambiguous_subject",),
        )
        self.assertEqual(
            receipts["control-matched-multiple-normals"].issue_codes,
            ("multiple_same_subject_normals",),
        )
        self.assertEqual(
            receipts["control-purity-invalid-row"].issue_codes,
            ("invalid_purity_ploidy_row",),
        )
        self.assertEqual(
            receipts["control-integrity-contamination"].issue_codes,
            ("contamination_flag",),
        )

    def test_evaluation_is_deterministic(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        first = evaluate_specimen_frontier_fixture(catalog)
        second = evaluate_specimen_frontier_fixture(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_invalid_row_receipts_have_unique_addresses(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][1]["payload"]["records"][0]["sample_id"] = ""
        payload["controls"][1]["payload"]["records"][0]["sample"] = ""
        payload["controls"][1]["parameters"]["required_issue_codes"] = ["invalid_specimen_row"]
        report = evaluate_specimen_frontier_fixture(
            SpecimenFrontierFixtureCatalog.from_mapping(payload)
        )
        invalid = [
            receipt for receipt in report.receipts if receipt.observed_result_state == "invalid"
        ]
        self.assertEqual(len(invalid), 1)
        self.assertEqual(len({receipt.output_address for receipt in invalid}), 1)

    def test_context_mutation_is_visible_in_fixture_checks(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["expected_state"] = "accepted"
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_frontier_fixture(catalog)
        failed = {check.check_id for check in report.checks if not check.passed}
        self.assertIn("control-ontology-conflicting-subject:fixture-state", failed)

    def test_payload_is_not_copied_into_operation_output(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["payload"]["records"][0]["extra_measurement"] = {"large": "value"}
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_frontier_fixture(catalog)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("extra_measurement", serialized)
        self.assertNotIn("large", serialized)

    def test_alias_subject_keys_support_aggregate_fixture_rows(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        record = copy.deepcopy(payload["positives"][0])
        record["record_id"] = "alias-subject-key"
        record["payload"]["records"][0]["subject_key"] = "entity-alias"
        payload["positives"].append(record)
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_frontier_fixture(catalog)
        receipt = next(item for item in report.receipts if item.record_id == "alias-subject-key")
        self.assertEqual(receipt.observed_result_state, "supported")


if __name__ == "__main__":
    unittest.main()
