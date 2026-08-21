from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog
from glio_noncode.specimen_beta_frontier_quality_gate import (
    evaluate_specimen_beta_frontier_quality_gate,
)

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")


class SpecimenBetaFrontierQualityGateTests(unittest.TestCase):
    def test_canonical_quality_gate_has_21_passing_checks(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_quality_gate(catalog)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 21)
        self.assertEqual(report.failed_check_ids, ())

    def test_quality_gate_exposes_lineage_and_evaluation_addresses(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        report = evaluate_specimen_beta_frontier_quality_gate(catalog)
        self.assertTrue(report.evaluation_address.startswith("sha256:"))
        self.assertTrue(report.scenario_address.startswith("sha256:"))
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_context_drift_fails_quality_gate(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["context_key"] = (
            "GRCh38|diffuse_glioma|adult|other|tumor_core|pre_treatment"
        )
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_beta_frontier_quality_gate(catalog)
        self.assertFalse(report.passed)
        self.assertIn("data-audit", report.failed_check_ids)

    def test_expected_counts_drift_fails_quality_gate(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["positives"][0]["expected_counts"]["somatic"] = 0
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_beta_frontier_quality_gate(catalog)
        self.assertFalse(report.passed)
        self.assertIn("fixture-evaluation", report.failed_check_ids)

    def test_quality_gate_requires_all_control_rows_to_be_review(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["expected_fixture_state"] = "accepted"
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_beta_frontier_quality_gate(catalog)
        self.assertFalse(report.passed)
        self.assertIn("issue-control-coverage", report.failed_check_ids)

    def test_quality_gate_is_deterministic(self) -> None:
        catalog = SpecimenBetaFrontierFixtureCatalog.from_file(FIXTURE)
        first = evaluate_specimen_beta_frontier_quality_gate(catalog)
        second = evaluate_specimen_beta_frontier_quality_gate(catalog)
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
