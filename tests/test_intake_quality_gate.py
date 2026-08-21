"""Combined quality-gate tests for the Domain 01 intake evidence stack."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.intake_quality_gate import IntakeQualityGate, evaluate_intake_quality_gate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "intake-public-aggregate.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class IntakeQualityGateTests(unittest.TestCase):
    def test_quality_gate_passes_and_reconciles_all_components(self) -> None:
        report = evaluate_intake_quality_gate(FIXTURE_PATH)
        self.assertTrue(report.passed)
        self.assertEqual(report.state.value, "accepted")
        self.assertEqual(len(report.checks), 14)
        self.assertEqual(len(report.failed_check_ids), 0)
        self.assertEqual(
            set(report.component_receipts),
            {"fixture", "data", "replay", "scenarios", "contracts"},
        )
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_quality_checks_are_unique_and_all_pass(self) -> None:
        report = IntakeQualityGate().evaluate_file(FIXTURE_PATH)
        self.assertEqual(len(report.checks), len({check.check_id for check in report.checks}))
        self.assertEqual(set(report.passed_check_ids), {check.check_id for check in report.checks})
        self.assertTrue(all(check.passed for check in report.checks))

    def test_expected_floors_match_fixture_components(self) -> None:
        gate = IntakeQualityGate()
        report = gate.evaluate_file(FIXTURE_PATH)
        self.assertEqual(report.component_receipts["fixture"]["check_count"], 33)
        self.assertEqual(report.component_receipts["data"]["record_count"], 4)
        self.assertEqual(report.component_receipts["data"]["control_count"], 8)
        self.assertEqual(report.component_receipts["scenarios"]["scenario_count"], 12)
        self.assertEqual(report.component_receipts["contracts"]["contract_count"], 4)

    def test_quality_gate_is_deterministic(self) -> None:
        first = evaluate_intake_quality_gate(FIXTURE_PATH)
        second = evaluate_intake_quality_gate(FIXTURE_PATH)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_patient_scope_mutation_fails_data_and_fixture_checks(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["provenance"]["patient_level_data"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = evaluate_intake_quality_gate(path)
        self.assertFalse(report.passed)
        self.assertIn("fixture-evaluation", report.failed_check_ids)
        self.assertIn("public-data-audit", report.failed_check_ids)

    def test_context_mutation_fails_replay_and_data_checks(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"][1]["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = evaluate_intake_quality_gate(path)
        self.assertFalse(report.passed)
        self.assertIn("fixture-evaluation", report.failed_check_ids)
        self.assertIn("public-data-audit", report.failed_check_ids)
        self.assertIn("replay-integrity", report.failed_check_ids)

    def test_control_floor_mutation_is_not_hidden(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["negative_controls"] = raw["negative_controls"][:2]
        raw["expected_negative_control_count"] = 2
        raw["provenance"]["expected_control_count"] = 2
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reduced.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = evaluate_intake_quality_gate(path)
        self.assertFalse(report.passed)
        self.assertIn("fixture-check-floor", report.failed_check_ids)
        self.assertIn("negative-control-count", report.failed_check_ids)
        self.assertIn("scenario-matrix", report.failed_check_ids)

    def test_positive_public_identifier_collision_fails_gate(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"][1]["public_identifier"] = raw["records"][0]["public_identifier"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "collision.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = evaluate_intake_quality_gate(path)
        self.assertFalse(report.passed)
        self.assertIn("public-identity-uniqueness", report.failed_check_ids)


if __name__ == "__main__":
    unittest.main()
