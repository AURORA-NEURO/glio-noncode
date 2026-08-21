"""Scenario matrix tests for Domain 02 C09-C12."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_haplotype_public_data import StructuralHaplotypeFixtureCatalog
from glio_noncode.structural_haplotype_scenario_matrix import (
    evaluate_structural_haplotype_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-haplotype-public-aggregate.json"


class StructuralHaplotypeScenarioTests(unittest.TestCase):
    def test_matrix_has_four_positives_and_eight_review_controls(self) -> None:
        matrix = evaluate_structural_haplotype_scenarios(str(FIXTURE))
        self.assertTrue(matrix.passed)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertEqual(matrix.positive_count, 4)
        self.assertEqual(matrix.review_count, 8)
        self.assertTrue(all(item.passed for item in matrix.scenarios))

    def test_scenarios_are_sorted_and_addressed(self) -> None:
        matrix = evaluate_structural_haplotype_scenarios(str(FIXTURE))
        self.assertEqual(tuple(item.scenario_id for item in matrix.scenarios), tuple(sorted(item.scenario_id for item in matrix.scenarios)))
        self.assertTrue(all(item.output_address.startswith("sha256:") for item in matrix.scenarios))
        self.assertRegex(matrix.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_expected_control_states_are_retained(self) -> None:
        matrix = evaluate_structural_haplotype_scenarios(str(FIXTURE))
        by_id = {item.record_id: item for item in matrix.scenarios}
        self.assertEqual(by_id["control-phased-unphased"].observed_result_state, "ambiguous")
        self.assertEqual(by_id["control-allele-conflict"].observed_result_state, "contradictory")
        self.assertEqual(by_id["control-pangenome-unmapped"].counts["unmapped"], 1)
        self.assertEqual(by_id["control-repeat-mixed-classes"].observed_result_state, "ambiguous")

    def test_matrix_is_deterministic(self) -> None:
        first = evaluate_structural_haplotype_scenarios(str(FIXTURE))
        second = evaluate_structural_haplotype_scenarios(str(FIXTURE))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_result_state_drift_fails_only_changed_scenario(self) -> None:
        raw = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
        raw["positives"][0]["expected_result_state"] = "ambiguous"
        matrix = evaluate_structural_haplotype_scenarios(StructuralHaplotypeFixtureCatalog.from_mapping(raw))
        self.assertFalse(matrix.passed)
        changed = next(item for item in matrix.scenarios if item.record_id == "positive-phased-haplotype")
        self.assertFalse(changed.passed)
        self.assertTrue(sum(not item.passed for item in matrix.scenarios) == 1)


if __name__ == "__main__":
    unittest.main()
