"""Quality gate reconciliation tests for Domain 02 C13-C16."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_frontier_public_data import (
    StructuralFrontierFixtureCatalog,
    StructuralFrontierFixtureState,
)
from glio_noncode.structural_frontier_quality_gate import evaluate_structural_frontier_quality_gate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"


class StructuralFrontierQualityGateTests(unittest.TestCase):
    def test_quality_gate_passes_with_twenty_checks(self) -> None:
        report = evaluate_structural_frontier_quality_gate(FIXTURE.as_posix())
        self.assertEqual(report.state, StructuralFrontierFixtureState.ACCEPTED)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 20)
        self.assertTrue(all(check.passed for check in report.checks))
        self.assertRegex(report.lineage_address, r"^sha256:[0-9a-f]{64}$")

    def test_quality_gate_rejects_sensitive_payload_scope(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["payload"]["records"][0]["patient_id"] = "restricted"
        report = evaluate_structural_frontier_quality_gate(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertEqual(report.state, StructuralFrontierFixtureState.REVIEW)
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "data-audit").passed)

    def test_quality_gate_rejects_missing_operation(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"] = [item for item in raw["positives"] if item["operation"] != "structural_evidence_export"]
        raw["controls"] = [item for item in raw["controls"] if item["operation"] != "structural_evidence_export"]
        report = evaluate_structural_frontier_quality_gate(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "operation-coverage").passed)

    def test_quality_gate_rejects_expected_count_drift(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][1]["expected_counts"]["compatible"] = 99
        report = evaluate_structural_frontier_quality_gate(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "fixture-evaluation").passed)

    def test_quality_gate_rejects_context_drift(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["controls"][2]["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        report = evaluate_structural_frontier_quality_gate(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertFalse(report.passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "data-audit").passed)
        self.assertFalse(next(check for check in report.checks if check.check_id == "context-agreement").passed)

    def test_quality_gate_exposes_contract_and_lineage_checks(self) -> None:
        report = evaluate_structural_frontier_quality_gate(FIXTURE.as_posix())
        for check_id in ("contract-floor", "contract-state-coverage", "lineage-audit", "lineage-shape"):
            self.assertTrue(next(check for check in report.checks if check.check_id == check_id).passed)

    def test_quality_gate_is_deterministic(self) -> None:
        first = evaluate_structural_frontier_quality_gate(FIXTURE.as_posix())
        second = evaluate_structural_frontier_quality_gate(FIXTURE.as_posix())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_quality_gate_addresses_all_component_reports(self) -> None:
        report = evaluate_structural_frontier_quality_gate(FIXTURE.as_posix())
        for address in (report.evaluation_address, report.replay_address, report.scenario_address, report.lineage_address, report.content_address):
            self.assertRegex(address, r"^sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
