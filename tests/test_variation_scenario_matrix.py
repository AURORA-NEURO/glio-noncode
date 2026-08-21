from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.variation_public_data import VariationDataState
from glio_noncode.variation_scenario_matrix import (
    VariationScenarioClass,
    VariationScenarioMatrix,
    evaluate_variation_scenarios,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "variation-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class VariationScenarioMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.matrix = VariationScenarioMatrix(self.raw)

    def test_matrix_contains_five_positive_and_five_review_scenarios(self) -> None:
        scenarios = self.matrix.scenarios()
        self.assertEqual(len(scenarios), 10)
        self.assertEqual(
            sum(s.scenario_class == VariationScenarioClass.POSITIVE for s in scenarios),
            5,
        )
        self.assertEqual(
            sum(s.scenario_class == VariationScenarioClass.REVIEW for s in scenarios),
            5,
        )

    def test_positive_scenarios_preserve_declared_states(self) -> None:
        scenarios = self.matrix.scenarios()[:5]
        self.assertEqual(
            tuple(s.expected_state for s in scenarios),
            ("supported", "supported", "supported", "supported", "ambiguous"),
        )
        self.assertEqual(
            tuple(s.scenario_id for s in scenarios),
            (
                "dbsnp:rs121913502:vrs",
                "categorical:rs121913502",
                "annotation:rs121913502",
                "multiallelic:rs121913502",
                "repeat-window:public-reference-01",
            ),
        )

    def test_review_scenarios_retain_required_issue_codes(self) -> None:
        scenarios = self.matrix.scenarios()[5:]
        by_id = {scenario.scenario_id: scenario for scenario in scenarios}
        self.assertEqual(
            by_id["negative:categorical-label-only"].required_issue_codes,
            ("category_not_resolved",),
        )
        self.assertEqual(
            by_id["negative:multiallelic-symbolic"].required_issue_codes,
            ("invalid_alternate",),
        )
        self.assertEqual(
            by_id["negative:repeat-reference-mismatch"].required_issue_codes,
            ("reference_mismatch",),
        )

    def test_matrix_passes_all_state_transitions(self) -> None:
        report = self.matrix.run()
        self.assertTrue(report.passed)
        self.assertEqual(report.state, VariationDataState.ACCEPTED)
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.failed_scenario_ids, ())
        self.assertEqual(len(report.positive_scenario_ids), 5)
        self.assertEqual(len(report.review_scenario_ids), 5)

    def test_matrix_results_have_stable_addresses_and_issue_codes(self) -> None:
        report = self.matrix.run()
        for result in report.results:
            self.assertTrue(result.passed)
            self.assertRegex(result.content_address, r"^sha256:[0-9a-f]{64}$")
            if result.required_issue_codes:
                self.assertTrue(
                    set(result.required_issue_codes).issubset(
                        set(result.observed_issue_codes)
                    )
                )

    def test_matrix_serialization_contains_counts_and_verdict(self) -> None:
        payload = self.matrix.run().to_dict()
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["state"], "accepted")
        self.assertEqual(payload["scenario_count"], 10)
        self.assertEqual(len(payload["results"]), 10)

    def test_convenience_function_matches_matrix(self) -> None:
        expected = self.matrix.run().to_dict()
        actual = evaluate_variation_scenarios(FIXTURE).to_dict()
        self.assertEqual(actual, expected)

    def test_matrix_is_deterministic(self) -> None:
        first = evaluate_variation_scenarios(FIXTURE).to_dict()
        second = evaluate_variation_scenarios(FIXTURE).to_dict()
        self.assertEqual(first, second)

    def test_mutated_positive_record_fails_only_that_scenario(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"][0]["payload"]["alternate"] = "<DEL>"
        report = VariationScenarioMatrix(raw).run()
        self.assertFalse(report.passed)
        self.assertEqual(report.state, VariationDataState.REVIEW)
        self.assertEqual(report.failed_scenario_ids, ("dbsnp:rs121913502:vrs",))

    def test_mutated_review_control_stays_review_when_issue_remains(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["negative_controls"][4]["payload"]["variant"]["alternate"] = "TT"
        report = VariationScenarioMatrix(raw).run()
        self.assertTrue(report.passed)
        self.assertEqual(report.review_scenario_ids[-1], "negative:repeat-reference-mismatch")

    def test_missing_context_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw.pop("context")
        with self.assertRaises(ValidationError):
            VariationScenarioMatrix(raw)

    def test_invalid_fixture_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                VariationScenarioMatrix.from_file(path)

    def test_missing_control_payload_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["negative_controls"][0].pop("payload")
        matrix = VariationScenarioMatrix(raw)
        with self.assertRaises(ValidationError):
            matrix.scenarios()


if __name__ == "__main__":
    unittest.main()
