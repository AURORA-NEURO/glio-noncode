"""Quality-gate reconciliation tests for Domain 02 C05-C08."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_beta_public_data import (
    StructuralBetaFixtureCatalog,
    StructuralBetaFixtureState,
)
from glio_noncode.structural_beta_quality_gate import evaluate_structural_beta_quality_gate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"


class StructuralBetaQualityGateTests(unittest.TestCase):
    def test_quality_gate_passes_with_twenty_checks_and_lineage(self) -> None:
        report = evaluate_structural_beta_quality_gate(str(FIXTURE))
        self.assertEqual(report.state, StructuralBetaFixtureState.ACCEPTED)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 20)
        self.assertTrue(all(check.passed for check in report.checks))
        self.assertRegex(report.lineage_address, r"^sha256:[0-9a-f]{64}$")

    def test_quality_gate_rejects_sensitive_scope(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["payload"]["subject_id"] = "restricted"
        report = evaluate_structural_beta_quality_gate(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertEqual(report.state, StructuralBetaFixtureState.REVIEW)
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "data-audit").passed)

    def test_quality_gate_rejects_missing_operation(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"] = [item for item in raw["positives"] if item["operation"] != "ecdna"]
        raw["controls"] = [item for item in raw["controls"] if item["operation"] != "ecdna"]
        report = evaluate_structural_beta_quality_gate(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "operation-coverage").passed)

    def test_quality_gate_rejects_expected_count_drift(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["expected_counts"]["candidates"] = 99
        report = evaluate_structural_beta_quality_gate(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "fixture-evaluation").passed)

    def test_quality_gate_is_deterministic(self) -> None:
        first = evaluate_structural_beta_quality_gate(str(FIXTURE))
        second = evaluate_structural_beta_quality_gate(str(FIXTURE))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_quality_gate_exposes_contract_and_lineage_checks(self) -> None:
        report = evaluate_structural_beta_quality_gate(str(FIXTURE))
        self.assertTrue(next(check for check in report.checks if check.check_id == "contract-floor").passed)
        self.assertTrue(next(check for check in report.checks if check.check_id == "contract-state-coverage").passed)
        self.assertTrue(next(check for check in report.checks if check.check_id == "lineage-audit").passed)
        self.assertTrue(next(check for check in report.checks if check.check_id == "lineage-shape").passed)


if __name__ == "__main__":
    unittest.main()
