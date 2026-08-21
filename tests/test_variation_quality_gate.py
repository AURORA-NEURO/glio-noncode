from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.variation_public_data import VariationDataState
from glio_noncode.variation_quality_gate import (
    VariationQualityCheck,
    VariationQualityGate,
    evaluate_variation_quality_gate,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "variation-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class VariationQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.gate = VariationQualityGate()

    def test_checked_in_fixture_passes_combined_quality_gate(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, VariationDataState.ACCEPTED)
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.fixture_id, "variation-public-aggregate-001")
        self.assertEqual(report.failed_check_ids, ())

    def test_quality_gate_has_twelve_explicit_checks(self) -> None:
        payload = self.gate.evaluate_file(FIXTURE).to_dict()
        self.assertEqual(payload["check_count"], 12)
        self.assertEqual(payload["passed_count"], 12)
        self.assertEqual(payload["failed_count"], 0)
        self.assertEqual(
            [check["check_id"] for check in payload["checks"]],
            [
                "fixture-evaluation",
                "fixture-check-floor",
                "public-data-audit",
                "replay-integrity",
                "record-count",
                "negative-control-count",
                "scenario-matrix",
                "contract-inventory",
                "context-consistency",
                "source-consistency",
                "deterministic-evaluation",
                "output-boundary",
            ],
        )

    def test_component_receipts_include_three_reconciled_layers(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        self.assertEqual(
            set(report.component_receipts),
            {"fixture", "data", "replay", "scenarios", "contracts"},
        )
        self.assertEqual(report.component_receipts["fixture"]["check_count"], 29)
        self.assertEqual(report.component_receipts["data"]["record_count"], 5)
        self.assertEqual(report.component_receipts["replay"]["case_count"], 1)
        self.assertEqual(report.component_receipts["scenarios"]["scenario_count"], 10)
        self.assertEqual(report.component_receipts["contracts"]["contract_count"], 5)

    def test_quality_gate_is_deterministic(self) -> None:
        first = self.gate.evaluate_file(FIXTURE).to_dict()
        second = self.gate.evaluate_file(FIXTURE).to_dict()
        self.assertEqual(first, second)
        self.assertRegex(first["content_address"], r"^sha256:[0-9a-f]{64}$")

    def test_convenience_function_matches_gate(self) -> None:
        expected = self.gate.evaluate_file(FIXTURE).to_dict()
        actual = evaluate_variation_quality_gate(FIXTURE).to_dict()
        self.assertEqual(actual, expected)

    def test_failed_vrs_operation_reviews_gate(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["alternate"] = "<DEL>"
        report = self.gate.evaluator.evaluate(fixture)
        self.assertFalse(report.passed)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            gate_report = self.gate.evaluate_file(path)
        self.assertFalse(gate_report.passed)
        self.assertIn("fixture-evaluation", gate_report.failed_check_ids)
        self.assertIn("replay-integrity", gate_report.failed_check_ids)

    def test_sensitive_record_reviews_gate(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["records"][0]["payload"]["patient_id"] = "restricted"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensitive.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            report = self.gate.evaluate_file(path)
        self.assertFalse(report.passed)
        self.assertIn("public-data-audit", report.failed_check_ids)

    def test_record_count_drift_is_reviewed(self) -> None:
        class StrictGate(VariationQualityGate):
            expected_record_count = 6

        report = StrictGate().evaluate_file(FIXTURE)
        self.assertFalse(report.passed)
        self.assertIn("record-count", report.failed_check_ids)

    def test_negative_control_count_drift_is_reviewed(self) -> None:
        class StrictGate(VariationQualityGate):
            expected_negative_control_count = 6

        report = StrictGate().evaluate_file(FIXTURE)
        self.assertFalse(report.passed)
        self.assertIn("negative-control-count", report.failed_check_ids)

    def test_fixture_check_floor_drift_is_reviewed(self) -> None:
        class StrictGate(VariationQualityGate):
            expected_fixture_checks = 30

        report = StrictGate().evaluate_file(FIXTURE)
        self.assertFalse(report.passed)
        self.assertIn("fixture-check-floor", report.failed_check_ids)

    def test_quality_check_rejects_blank_metadata(self) -> None:
        with self.assertRaises(ValidationError):
            VariationQualityCheck(" ", "requirement", True, True, "detail")
        with self.assertRaises(ValidationError):
            VariationQualityCheck("check", " ", True, True, "detail")
        with self.assertRaises(ValidationError):
            VariationQualityCheck("check", "requirement", True, True, " ")

    def test_quality_gate_preserves_evidence_boundary(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        self.assertEqual(
            report.evidence_boundary,
            "public aggregate identity and deterministic software receipts only; "
            "no biological or clinical claim",
        )

    def test_quality_output_does_not_contain_restricted_values(self) -> None:
        serialized = json.dumps(
            self.gate.evaluate_file(FIXTURE).to_dict(), sort_keys=True
        ).casefold()
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("mrn", serialized)
        self.assertNotIn("secret", serialized)

    def test_quality_report_is_json_ready(self) -> None:
        payload = self.gate.evaluate_file(FIXTURE).to_dict()
        encoded = json.dumps(payload, sort_keys=True)
        decoded = json.loads(encoded)
        self.assertTrue(decoded["passed"])
        self.assertEqual(decoded["state"], "accepted")


if __name__ == "__main__":
    unittest.main()
