"""Quality-gate reconciliation tests for the structural evidence stack."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_public_data import StructuralFixtureCatalog, StructuralFixtureState
from glio_noncode.structural_quality_gate import evaluate_structural_quality_gate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-public-aggregate.json"


class StructuralQualityGateTests(unittest.TestCase):
    def test_quality_gate_passes_and_has_seventeen_checks(self) -> None:
        report = evaluate_structural_quality_gate(str(FIXTURE))
        self.assertEqual(report.state, StructuralFixtureState.ACCEPTED)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 17)
        self.assertTrue(all(check.passed for check in report.checks))
        self.assertRegex(report.evaluation_address, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(report.replay_address, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(report.scenario_address, r"^sha256:[0-9a-f]{64}$")

    def test_quality_gate_rejects_sensitive_scope(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["sources"][0]["patient_level"] = False
        raw["positives"][0]["payload"]["subject_id"] = "restricted"
        report = evaluate_structural_quality_gate(StructuralFixtureCatalog.from_mapping(raw))
        self.assertEqual(report.state, StructuralFixtureState.REVIEW)
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "data-audit").passed)

    def test_quality_gate_rejects_missing_operation(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"] = [item for item in raw["positives"] if item["operation"] != "consensus"]
        catalog = StructuralFixtureCatalog.from_mapping(raw)
        report = evaluate_structural_quality_gate(catalog)
        self.assertFalse(report.passed)
        operation_check = next(check for check in report.checks if check.check_id == "positive-operation-coverage")
        self.assertFalse(operation_check.passed)

    def test_quality_gate_rejects_expected_count_drift(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][3]["expected_counts"]["output_segments"] = 99
        report = evaluate_structural_quality_gate(StructuralFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "fixture-evaluation").passed)

    def test_quality_gate_determinism_check_is_true_for_same_catalog(self) -> None:
        report = evaluate_structural_quality_gate(str(FIXTURE))
        check = next(check for check in report.checks if check.check_id == "determinism")
        self.assertTrue(check.passed)
        self.assertEqual(check.expected, check.observed)

    def test_quality_gate_addresses_are_stable(self) -> None:
        first = evaluate_structural_quality_gate(str(FIXTURE))
        second = evaluate_structural_quality_gate(str(FIXTURE))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_quality_gate_contract_and_source_checks_are_explicit(self) -> None:
        report = evaluate_structural_quality_gate(str(FIXTURE))
        self.assertTrue(next(check for check in report.checks if check.check_id == "contract-floor").passed)
        self.assertTrue(next(check for check in report.checks if check.check_id == "source-agreement").passed)
        self.assertTrue(next(check for check in report.checks if check.check_id == "aggregate-scope").passed)


if __name__ == "__main__":
    unittest.main()
