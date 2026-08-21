"""Scenario-matrix tests for Domain 02 C05-C08."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_beta_public_data import StructuralBetaFixtureCatalog
from glio_noncode.structural_beta_scenario_matrix import evaluate_structural_beta_scenarios

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"


class StructuralBetaScenarioMatrixTests(unittest.TestCase):
    def test_matrix_has_four_positive_and_eight_review_scenarios(self) -> None:
        matrix = evaluate_structural_beta_scenarios(str(FIXTURE))
        self.assertTrue(matrix.passed)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertEqual(matrix.positive_count, 4)
        self.assertEqual(matrix.review_count, 8)
        self.assertEqual(len({scenario.scenario_id for scenario in matrix.scenarios}), 12)

    def test_matrix_preserves_expected_ambiguity_and_abstention(self) -> None:
        matrix = evaluate_structural_beta_scenarios(str(FIXTURE))
        by_id = {scenario.record_id: scenario for scenario in matrix.scenarios}
        self.assertEqual(by_id["positive-enhancer-hijacking"].observed_result_state, "ambiguous")
        self.assertEqual(by_id["control-focal-no-amplification"].observed_result_state, "abstained")
        self.assertEqual(by_id["control-enhancer-context-mismatch"].observed_result_state, "out_of_domain")

    def test_matrix_is_independently_deterministic(self) -> None:
        first = evaluate_structural_beta_scenarios(str(FIXTURE))
        second = evaluate_structural_beta_scenarios(str(FIXTURE))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_matrix_fails_when_positive_expectation_drifts(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][3]["expected_result_state"] = "supported"
        matrix = evaluate_structural_beta_scenarios(StructuralBetaFixtureCatalog.from_mapping(raw))
        self.assertFalse(matrix.passed)
        self.assertFalse(
            next(item for item in matrix.scenarios if item.record_id == "positive-enhancer-hijacking").passed
        )


if __name__ == "__main__":
    unittest.main()
