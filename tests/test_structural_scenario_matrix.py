"""Independent scenario matrix tests for Domain 02."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_public_data import StructuralFixtureCatalog, StructuralFixtureState
from glio_noncode.structural_scenario_matrix import evaluate_structural_scenarios

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-public-aggregate.json"


class StructuralScenarioMatrixTests(unittest.TestCase):
    def test_matrix_contains_four_positive_and_eight_review_cases(self) -> None:
        matrix = evaluate_structural_scenarios(str(FIXTURE))
        self.assertTrue(matrix.passed)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertEqual(matrix.positive_count, 4)
        self.assertEqual(matrix.review_count, 8)
        self.assertRegex(matrix.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_scenarios_are_individually_addressed(self) -> None:
        matrix = evaluate_structural_scenarios(str(FIXTURE))
        self.assertEqual(
            len({scenario.output_address for scenario in matrix.scenarios}),
            len(matrix.scenarios),
        )
        self.assertTrue(all(scenario.scenario_id.startswith("scenario:") for scenario in matrix.scenarios))

    def test_positive_and_review_state_sets_are_separate(self) -> None:
        matrix = evaluate_structural_scenarios(str(FIXTURE))
        positives = [item for item in matrix.scenarios if item.expected_state == StructuralFixtureState.ACCEPTED]
        reviews = [item for item in matrix.scenarios if item.expected_state == StructuralFixtureState.REVIEW]
        self.assertTrue(all(item.passed for item in positives))
        self.assertTrue(all(item.passed for item in reviews))
        self.assertTrue(all(item.observed_state == StructuralFixtureState.REVIEW for item in reviews))

    def test_required_issue_codes_are_not_hidden_in_scenarios(self) -> None:
        matrix = evaluate_structural_scenarios(str(FIXTURE))
        for scenario in matrix.scenarios:
            self.assertTrue(set(scenario.required_issue_codes).issubset(scenario.observed_issue_codes))

    def test_context_drift_changes_scenario_pass_state(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["controls"][0]["context_key"] = raw["context_key"].replace("GRCh38", "GRCh37")
        matrix = evaluate_structural_scenarios(StructuralFixtureCatalog.from_mapping(raw))
        changed = next(item for item in matrix.scenarios if item.record_id == raw["controls"][0]["record_id"])
        self.assertFalse(changed.passed)
        self.assertEqual(changed.observed_result_state, "review-issue")

    def test_result_is_deterministic(self) -> None:
        first = evaluate_structural_scenarios(str(FIXTURE))
        second = evaluate_structural_scenarios(str(FIXTURE))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_mutating_expected_result_state_is_detected(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["positives"][2]["expected_result_state"] = "supported"
        matrix = evaluate_structural_scenarios(StructuralFixtureCatalog.from_mapping(copy.deepcopy(raw)))
        self.assertFalse(matrix.passed)
        changed = next(item for item in matrix.scenarios if item.record_id == "positive-complex")
        self.assertFalse(changed.passed)


if __name__ == "__main__":
    unittest.main()
