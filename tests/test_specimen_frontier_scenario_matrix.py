"""Independent scenario matrix tests for Domain 03 C01-C04."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.specimen_frontier_public_data import SpecimenFrontierFixtureCatalog
from glio_noncode.specimen_frontier_scenario_matrix import evaluate_specimen_frontier_scenarios

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"


class SpecimenFrontierScenarioTests(unittest.TestCase):
    def test_canonical_matrix_has_twelve_passing_scenarios(self) -> None:
        matrix = evaluate_specimen_frontier_scenarios(str(FIXTURE))
        self.assertTrue(matrix.passed)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertEqual(matrix.positive_count, 4)
        self.assertEqual(matrix.review_count, 8)
        self.assertTrue(all(scenario.passed for scenario in matrix.scenarios))

    def test_scenarios_are_independent_and_addressed(self) -> None:
        matrix = evaluate_specimen_frontier_scenarios(
            SpecimenFrontierFixtureCatalog.from_file(FIXTURE)
        )
        self.assertEqual(
            [scenario.scenario_id for scenario in matrix.scenarios],
            [f"scenario:{scenario.record_id}" for scenario in matrix.scenarios],
        )
        self.assertTrue(matrix.content_address.startswith("sha256:"))

    def test_expected_control_transitions_are_present(self) -> None:
        matrix = evaluate_specimen_frontier_scenarios(str(FIXTURE))
        by_id = {scenario.record_id: scenario for scenario in matrix.scenarios}
        self.assertEqual(
            by_id["control-ontology-conflicting-subject"].observed_result_state, "ambiguous"
        )
        self.assertEqual(by_id["control-matched-missing-normal"].observed_result_state, "abstained")
        self.assertEqual(by_id["control-purity-invalid-row"].observed_result_state, "review")
        self.assertEqual(
            by_id["control-integrity-subject-mismatch"].observed_result_state, "flagged"
        )

    def test_mutated_expected_state_fails_matrix(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["controls"][0]["expected_result_state"] = "supported"
        catalog = SpecimenFrontierFixtureCatalog.from_mapping(payload)
        matrix = evaluate_specimen_frontier_scenarios(catalog)
        self.assertFalse(matrix.passed)
        failed = next(
            scenario
            for scenario in matrix.scenarios
            if scenario.record_id == "control-ontology-conflicting-subject"
        )
        self.assertFalse(failed.passed)


if __name__ == "__main__":
    unittest.main()
