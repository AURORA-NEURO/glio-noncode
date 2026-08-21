from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.specimen_beta_frontier_public_data import SpecimenBetaFrontierFixtureCatalog
from glio_noncode.specimen_beta_frontier_scenario_matrix import (
    evaluate_specimen_beta_frontier_scenarios,
)

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")


class SpecimenBetaFrontierScenarioMatrixTests(unittest.TestCase):
    def test_matrix_has_twelve_passing_scenarios(self) -> None:
        report = evaluate_specimen_beta_frontier_scenarios(FIXTURE)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.scenarios), 12)
        self.assertEqual(report.operation_count, 4)

    def test_matrix_retains_expected_control_states(self) -> None:
        report = evaluate_specimen_beta_frontier_scenarios(FIXTURE)
        by_id = {scenario.record_id: scenario for scenario in report.scenarios}
        self.assertEqual(
            by_id["control-origin-conflicting-presence"].observed_result_state, "ambiguous"
        )
        self.assertEqual(by_id["control-mosaic-single-tissue"].observed_result_state, "partial")
        self.assertEqual(by_id["control-ccf-out-of-range"].observed_result_state, "partial")
        self.assertEqual(by_id["control-subclone-boundary"].observed_result_state, "ambiguous")

    def test_mutated_expected_state_fails_matrix(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["expected_result_state"] = "supported"
        catalog = SpecimenBetaFrontierFixtureCatalog.from_mapping(payload)
        report = evaluate_specimen_beta_frontier_scenarios(catalog)
        self.assertFalse(report.passed)

    def test_matrix_address_is_deterministic(self) -> None:
        first = evaluate_specimen_beta_frontier_scenarios(FIXTURE)
        second = evaluate_specimen_beta_frontier_scenarios(FIXTURE)
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()
