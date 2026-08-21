from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.identity_fixture_eval import (
    IdentityFixtureEvaluator,
    IdentityOperationFailure,
    evaluate_identity_fixture,
)
from glio_noncode.identity_public_data import IdentityDataState

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "identity-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class IdentityFixtureEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = IdentityFixtureEvaluator()
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_checked_in_fixture_passes_all_detailed_checks(self) -> None:
        report = evaluate_identity_fixture(FIXTURE)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, IdentityDataState.ACCEPTED)
        self.assertEqual(len(report.checks), 37)
        self.assertEqual(report.failed_check_ids, ())
        self.assertEqual(len(report.positive_reports), 4)
        self.assertEqual(len(report.negative_reports), 8)

    def test_positive_reports_cover_four_operation_states(self) -> None:
        report = evaluate_identity_fixture(FIXTURE)
        self.assertEqual(report.positive_reports["equivalence:rs121913502"]["state"], "supported")
        self.assertEqual(
            report.positive_reports["reconciliation:rs121913502"]["state"],
            "partial",
        )
        self.assertEqual(
            report.positive_reports["sample:public-aggregate-01"]["state"],
            "supported",
        )
        self.assertEqual(
            report.positive_reports["custody:public-aggregate-artifact-01"]["state"],
            "supported",
        )

    def test_negative_reports_retain_each_declared_boundary_state(self) -> None:
        report = evaluate_identity_fixture(FIXTURE)
        states = {key: value["state"] for key, value in report.negative_reports.items()}
        self.assertEqual(states["equivalence:out-of-domain-build"], "out_of_domain")
        self.assertEqual(states["equivalence:absent-query"], "absent")
        self.assertEqual(states["reconciliation:ambiguous-alias"], "ambiguous")
        self.assertEqual(states["reconciliation:duplicate-record-id"], "abstained")
        self.assertEqual(states["sample:cross-subject"], "contradictory")
        self.assertEqual(states["sample:missing-subject"], "contradictory")
        self.assertEqual(states["custody:broken-link"], "contradictory")
        self.assertEqual(states["custody:invalid-timestamp"], "abstained")

    def test_negative_reports_expose_required_issue_codes(self) -> None:
        report = evaluate_identity_fixture(FIXTURE)
        ambiguous = json.dumps(report.negative_reports["reconciliation:ambiguous-alias"])
        self.assertIn("ambiguous_aliases", ambiguous)
        cross_subject = json.dumps(report.negative_reports["sample:cross-subject"])
        self.assertIn("sample_maps_to_multiple_subjects", cross_subject)
        broken = json.dumps(report.negative_reports["custody:broken-link"])
        self.assertIn("hash_continuity_gap", broken)
        invalid_time = report.negative_reports["custody:invalid-timestamp"]
        self.assertEqual(invalid_time["error_code"], "validation_error")

    def test_outputs_are_addressed_and_deterministic(self) -> None:
        first = evaluate_identity_fixture(FIXTURE)
        second = evaluate_identity_fixture(FIXTURE)
        self.assertEqual(first.content_address, second.content_address)
        for output in (*first.positive_reports.values(), *first.negative_reports.values()):
            self.assertTrue(str(output["content_address"]).startswith("sha256:"))

    def test_data_boundary_report_is_embedded(self) -> None:
        report = evaluate_identity_fixture(FIXTURE)
        self.assertTrue(report.data_report["accepted"])
        self.assertEqual(report.data_report["positive_count"], 4)
        self.assertEqual(report.data_report["negative_control_count"], 8)
        self.assertEqual(report.context_key, CONTEXT)

    def test_missing_operation_kind_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"] = fixture["records"][:3]
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(fixture)

    def test_missing_negative_controls_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"] = []
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(fixture)

    def test_malformed_control_becomes_validation_abstention(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"][-1]["payload"]["events"][0]["occurred_at"] = "bad-time"
        report = self.evaluator.evaluate(fixture)
        self.assertEqual(
            report.negative_reports["custody:invalid-timestamp"]["state"],
            "abstained",
        )
        self.assertTrue(report.passed)

    def test_positive_payload_mutation_fails_declared_state_check(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["query"] = "missing-public-query"
        report = self.evaluator.evaluate(fixture)
        self.assertFalse(report.passed)
        self.assertIn("positive:equivalence:rs121913502", report.failed_check_ids)

    def test_restricted_output_boundary_is_checked(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["patient_id"] = "restricted"
        report = self.evaluator.evaluate(fixture)
        self.assertFalse(report.passed)
        self.assertIn("data-boundary:identity-catalog", report.failed_check_ids)

    def test_run_record_exposes_a_serializable_operation(self) -> None:
        catalog = self.evaluator.validate_fixture(self.fixture)
        record = catalog.record("sample:public-aggregate-01")
        self.assertIsNotNone(record)
        output = self.evaluator.run_record(record, CONTEXT)
        self.assertEqual(output.state.value, "supported")
        self.assertTrue(output.to_dict()["content_address"].startswith("sha256:"))

    def test_run_control_returns_failure_receipt_for_validation_error(self) -> None:
        catalog = self.evaluator.validate_fixture(self.fixture)
        control = catalog.control("custody:invalid-timestamp")
        self.assertIsNotNone(control)
        output = self.evaluator.run_control(control, CONTEXT)
        self.assertIsInstance(output, IdentityOperationFailure)
        self.assertEqual(output.state, "abstained")
        self.assertEqual(output.error_code, "validation_error")

    def test_report_to_dict_contains_check_counts(self) -> None:
        payload = evaluate_identity_fixture(FIXTURE).to_dict()
        self.assertEqual(payload["check_count"], 37)
        self.assertEqual(payload["passed_count"], 37)
        self.assertEqual(payload["failed_count"], 0)
        self.assertTrue(payload["passed"])

    def test_restricted_values_are_not_copied_to_failed_reports(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["patient_id"] = "do-not-return"
        report = self.evaluator.evaluate(fixture)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("do-not-return", serialized)


if __name__ == "__main__":
    unittest.main()
