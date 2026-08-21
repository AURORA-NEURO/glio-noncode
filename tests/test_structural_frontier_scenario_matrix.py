"""Scenario matrix tests for Domain 02 C13-C16."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.structural_frontier_public_data import StructuralFrontierFixtureState
from glio_noncode.structural_frontier_scenario_matrix import evaluate_structural_frontier_scenarios

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"


class StructuralFrontierScenarioTests(unittest.TestCase):
    def test_canonical_matrix_has_twelve_passing_scenarios(self) -> None:
        matrix = evaluate_structural_frontier_scenarios(FIXTURE.as_posix())
        self.assertTrue(matrix.passed)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertEqual(matrix.positive_count, 4)
        self.assertEqual(matrix.review_count, 8)
        self.assertTrue(all(scenario.passed for scenario in matrix.scenarios))

    def test_matrix_keeps_both_fixture_states(self) -> None:
        matrix = evaluate_structural_frontier_scenarios(FIXTURE.as_posix())
        self.assertEqual(
            {scenario.expected_fixture_state for scenario in matrix.scenarios},
            {StructuralFrontierFixtureState.ACCEPTED, StructuralFrontierFixtureState.REVIEW},
        )
        self.assertEqual(
            {scenario.observed_fixture_state for scenario in matrix.scenarios},
            {StructuralFrontierFixtureState.ACCEPTED, StructuralFrontierFixtureState.REVIEW},
        )

    def test_matrix_covers_all_operations(self) -> None:
        matrix = evaluate_structural_frontier_scenarios(FIXTURE.as_posix())
        self.assertEqual({scenario.operation.value for scenario in matrix.scenarios}, {
            "tandem_repeat", "compound_haplotype", "breakpoint_uncertainty", "structural_evidence_export"
        })

    def test_scenario_issue_codes_remain_visible(self) -> None:
        matrix = evaluate_structural_frontier_scenarios(FIXTURE.as_posix())
        by_id = {scenario.scenario_id: scenario for scenario in matrix.scenarios}
        self.assertIn("invalid_motif", by_id["scenario:control-tandem-invalid-motif"].issue_codes)
        self.assertIn("incomplete_haplotype", by_id["scenario:control-compound-incomplete"].issue_codes)
        self.assertIn("inverted_left_interval", by_id["scenario:control-breakpoint-inverted"].issue_codes)
        self.assertIn("validation_error", by_id["scenario:control-export-missing-field"].issue_codes)

    def test_matrix_detects_expected_result_drift(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["controls"][0]["expected_result_state"] = "accepted"
        from glio_noncode.structural_frontier_public_data import StructuralFrontierFixtureCatalog

        matrix = evaluate_structural_frontier_scenarios(StructuralFrontierFixtureCatalog.from_mapping(raw))
        self.assertFalse(matrix.passed)
        self.assertFalse(next(item for item in matrix.scenarios if item.scenario_id == "scenario:control-tandem-invalid-motif").passed)

    def test_matrix_is_deterministic(self) -> None:
        first = evaluate_structural_frontier_scenarios(FIXTURE.as_posix())
        second = evaluate_structural_frontier_scenarios(FIXTURE.as_posix())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())


if __name__ == "__main__":
    unittest.main()
