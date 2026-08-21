"""Quality gate reconciliation tests for Domain 03 C01-C04."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.specimen_frontier_public_data import SpecimenFrontierFixtureCatalog
from glio_noncode.specimen_frontier_quality_gate import evaluate_specimen_frontier_quality_gate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"


class SpecimenFrontierQualityGateTests(unittest.TestCase):
    def test_canonical_quality_gate_passes_21_checks(self) -> None:
        report = evaluate_specimen_frontier_quality_gate(str(FIXTURE))
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 21)
        self.assertEqual(report.to_dict()["failed_check_ids"], ())

    def test_quality_gate_is_deterministic(self) -> None:
        catalog = SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        first = evaluate_specimen_frontier_quality_gate(catalog)
        second = evaluate_specimen_frontier_quality_gate(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_record_context_drift_fails_context_agreement(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        )
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_frontier_quality_gate(catalog)
        self.assertFalse(report.passed)
        failed = {check.check_id for check in report.checks if not check.passed}
        self.assertIn("data-audit", failed)
        self.assertIn("context-agreement", failed)

    def test_sensitive_payload_fails_data_and_sanitized_boundaries(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["payload"]["records"][0]["medical_record_number"] = "x"
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_frontier_quality_gate(catalog)
        self.assertFalse(report.passed)
        failed = {check.check_id for check in report.checks if not check.passed}
        self.assertIn("data-audit", failed)

    def test_quality_report_contains_all_component_addresses(self) -> None:
        report = evaluate_specimen_frontier_quality_gate(str(FIXTURE))
        self.assertTrue(report.evaluation_address.startswith("sha256:"))
        self.assertTrue(report.replay_address.startswith("sha256:"))
        self.assertTrue(report.scenario_address.startswith("sha256:"))
        self.assertTrue(report.lineage_address.startswith("sha256:"))
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_quality_gate_rejects_unexpected_positive_result(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_result_state"] = "ambiguous"
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_frontier_quality_gate(catalog)
        self.assertFalse(report.passed)
        self.assertIn("fixture-evaluation", report.to_dict()["failed_check_ids"])


if __name__ == "__main__":
    unittest.main()
