"""Executable fixture tests for the four Domain 01 intake adapters."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.intake_fixture_eval import (
    IntakeFixtureEvaluator,
    IntakeOperationFailure,
    _issue_codes,
    _state_value,
    evaluate_intake_fixture,
)
from glio_noncode.intake_public_data import IntakeFixtureCatalog, IntakeRecordKind

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "intake-public-aggregate.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class IntakeFixtureEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = IntakeFixtureEvaluator()

    def test_public_fixture_passes_with_thirty_three_checks(self) -> None:
        report = evaluate_intake_fixture(FIXTURE_PATH)
        self.assertTrue(report.passed)
        self.assertEqual(report.check_count if hasattr(report, "check_count") else len(report.checks), 33)
        self.assertEqual(len(report.failed_check_ids), 0)
        self.assertEqual(len(report.positive_reports), 4)
        self.assertEqual(len(report.negative_reports), 8)
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_positive_states_cover_all_operation_outputs(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE_PATH)
        states = {record_id: value["state"] for record_id, value in report.positive_reports.items()}
        self.assertEqual(
            states,
            {
                "consent-clinvar-public-use": "accepted",
                "anomaly-clinvar-rs121913502": "accepted",
                "completeness-clinvar-rs121913502": "accepted",
                "bundle-clinvar-public-intake": "published",
            },
        )
        for receipt in report.positive_reports.values():
            self.assertTrue(receipt["content_address"].startswith("sha256:"))
            self.assertIn("public_identifier", receipt)

    def test_negative_controls_preserve_expected_states_and_reasons(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE_PATH)
        self.assertEqual(report.negative_reports["consent-withdrawn"]["state"], "blocked")
        self.assertEqual(
            report.negative_reports["anomaly-duplicate-record"]["state"], "quarantined"
        )
        self.assertEqual(
            report.negative_reports["completeness-missing-fields"]["state"], "review"
        )
        self.assertEqual(report.negative_reports["bundle-blocked-state"]["state"], "review")
        for control_id, receipt in report.negative_reports.items():
            self.assertTrue(receipt["content_address"].startswith("sha256:"), control_id)
        self.assertIn(
            "consent_not_active",
            _issue_codes(report.negative_reports["consent-withdrawn"]),
        )
        self.assertIn(
            "duplicate_record_id",
            _issue_codes(report.negative_reports["anomaly-duplicate-record"]),
        )
        self.assertIn(
            "validation_error",
            _issue_codes(report.negative_reports["bundle-blocked-state"]),
        )

    def test_fixture_checks_have_unique_ids_and_addresses(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE_PATH)
        self.assertEqual(len(report.checks), len({check.check_id for check in report.checks}))
        self.assertTrue(all(check.content_address.startswith("sha256:") for check in report.checks))
        self.assertEqual(len(report.passed_check_ids), len(report.checks))

    def test_evaluation_is_deterministic(self) -> None:
        first = self.evaluator.evaluate_file(FIXTURE_PATH)
        second = self.evaluator.evaluate_file(FIXTURE_PATH)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_missing_record_kind_is_rejected_before_execution(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"] = [row for row in raw["records"] if row["kind"] != "bundle"]
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(raw)

    def test_duplicate_positive_operation_is_rejected(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"][1]["operation"] = raw["records"][0]["operation"]
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(raw)

    def test_bad_negative_control_shape_is_rejected(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["negative_controls"][0]["payload"] = []
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(raw)

    def test_bundle_operation_rejects_blocked_state_as_review_failure(self) -> None:
        catalog = IntakeFixtureCatalog.from_file(FIXTURE_PATH)
        record = catalog.control("bundle-blocked-state")
        assert record is not None
        output = self.evaluator.run_record(record.as_record(), {}, catalog.context_key)
        self.assertIsInstance(output, IntakeOperationFailure)
        self.assertEqual(output.state, "review")
        self.assertEqual(output.error_code, "validation_error")

    def test_run_record_can_inspect_each_positive_kind(self) -> None:
        catalog = IntakeFixtureCatalog.from_file(FIXTURE_PATH)
        context = {
            "genome_build": "GRCh38",
            "disease_class": "diffuse_glioma",
            "age_group": "adult",
            "cell_state": "malignant_oligodendrocyte_like",
            "territory": "tumor_core",
            "treatment_phase": "pre_treatment",
        }
        outputs = [self.evaluator.run_record(record, context, catalog.context_key) for record in catalog.records]
        self.assertEqual({record.kind for record in catalog.records}, set(IntakeRecordKind))
        self.assertTrue(all(_state_value(output) in {"accepted", "published"} for output in outputs))

    def test_positive_trace_identifiers_are_present_in_receipts(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE_PATH)
        catalog = IntakeFixtureCatalog.from_file(FIXTURE_PATH)
        for record in catalog.records:
            receipt = report.positive_reports[record.record_id]
            self.assertIn(record.public_identifier, json.dumps(receipt, sort_keys=True))

    def test_mutated_source_scope_fails_data_boundary_check(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["source_receipts"][0]["patient_level_data"] = True
        report = self.evaluator.evaluate(raw)
        self.assertFalse(report.passed)
        self.assertIn("data-boundary:intake-catalog", report.failed_check_ids)

    def test_mutated_context_fails_data_boundary_check(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"][0]["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        report = self.evaluator.evaluate(raw)
        self.assertFalse(report.passed)
        self.assertIn("data-boundary:intake-catalog", report.failed_check_ids)


if __name__ == "__main__":
    unittest.main()
