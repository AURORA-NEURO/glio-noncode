"""Independent scenario matrix tests for Domain 01 intake."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.intake_scenario_matrix import (
    IntakeScenarioClass,
    IntakeScenarioMatrix,
    evaluate_intake_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "intake-public-aggregate.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class IntakeScenarioMatrixTests(unittest.TestCase):
    def test_matrix_passes_with_four_positive_and_eight_review_scenarios(self) -> None:
        report = evaluate_intake_scenarios(FIXTURE_PATH)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.results), 12)
        self.assertEqual(len(report.positive_scenario_ids), 4)
        self.assertEqual(len(report.review_scenario_ids), 8)
        self.assertEqual(report.failed_scenario_ids, ())

    def test_scenarios_preserve_class_and_expected_states(self) -> None:
        matrix = IntakeScenarioMatrix(FIXTURE)
        scenarios = matrix.scenarios()
        self.assertEqual(
            sum(item.scenario_class == IntakeScenarioClass.POSITIVE for item in scenarios),
            4,
        )
        self.assertEqual(
            sum(item.scenario_class == IntakeScenarioClass.REVIEW for item in scenarios),
            8,
        )
        self.assertIn("published", {item.expected_state for item in scenarios})
        self.assertIn("blocked", {item.expected_state for item in scenarios})
        self.assertIn("quarantined", {item.expected_state for item in scenarios})

    def test_every_scenario_result_has_a_unique_content_address(self) -> None:
        report = evaluate_intake_scenarios(FIXTURE_PATH)
        self.assertEqual(
            len(report.results),
            len({result.content_address for result in report.results}),
        )
        self.assertTrue(
            all(result.content_address.startswith("sha256:") for result in report.results)
        )

    def test_scenario_matrix_is_deterministic(self) -> None:
        first = evaluate_intake_scenarios(FIXTURE_PATH)
        second = evaluate_intake_scenarios(FIXTURE_PATH)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_required_issue_code_mismatch_fails_only_that_control(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["negative_controls"][0]["required_issue_codes"] = ["missing-code"]
        report = IntakeScenarioMatrix(raw).run()
        self.assertFalse(report.passed)
        self.assertIn("negative:consent-withdrawn", report.failed_scenario_ids)
        self.assertEqual(len(report.failed_scenario_ids), 1)

    def test_expected_state_mutation_is_observable(self) -> None:
        raw = copy.deepcopy(FIXTURE)
        raw["records"][0]["expected_state"] = "review"
        report = IntakeScenarioMatrix(raw).run()
        self.assertFalse(report.passed)
        self.assertIn("consent-clinvar-public-use", report.failed_scenario_ids)


if __name__ == "__main__":
    unittest.main()
