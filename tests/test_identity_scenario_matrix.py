from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.identity_fixture_eval import IdentityFixtureEvaluator
from glio_noncode.identity_public_data import IdentityDataState
from glio_noncode.identity_scenario_matrix import (
    IdentityScenarioClass,
    IdentityScenarioMatrix,
    evaluate_identity_scenarios,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "identity-public-aggregate.json"


class IdentityScenarioMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_checked_in_matrix_passes_twelve_scenarios(self) -> None:
        report = evaluate_identity_scenarios(str(FIXTURE))
        self.assertTrue(report.passed)
        self.assertEqual(report.state, IdentityDataState.ACCEPTED)
        self.assertEqual(len(report.results), 12)
        self.assertEqual(report.failed_scenario_ids, ())

    def test_matrix_contains_four_positive_and_eight_review_cases(self) -> None:
        matrix = IdentityScenarioMatrix(self.raw)
        scenarios = matrix.scenarios()
        self.assertEqual(
            sum(item.scenario_class == IdentityScenarioClass.POSITIVE for item in scenarios),
            4,
        )
        self.assertEqual(
            sum(item.scenario_class == IdentityScenarioClass.REVIEW for item in scenarios),
            8,
        )

    def test_review_scenarios_retain_declared_states(self) -> None:
        report = IdentityScenarioMatrix(self.raw).run()
        observed = {
            result.scenario.scenario_id: result.observed_state
            for result in report.results
            if result.scenario.scenario_class == IdentityScenarioClass.REVIEW
        }
        self.assertEqual(observed["negative:equivalence:absent-query"], "absent")
        self.assertEqual(observed["negative:reconciliation:ambiguous-alias"], "ambiguous")
        self.assertEqual(observed["negative:sample:cross-subject"], "contradictory")
        self.assertEqual(observed["negative:custody:invalid-timestamp"], "abstained")

    def test_matrix_is_deterministic(self) -> None:
        first = IdentityScenarioMatrix(self.raw).run()
        second = IdentityScenarioMatrix(self.raw).run()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_mutating_positive_query_fails_only_the_affected_scenario(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"][0]["payload"]["query"] = "missing-query"
        report = IdentityScenarioMatrix(raw).run()
        self.assertFalse(report.passed)
        self.assertEqual(report.failed_scenario_ids, ("equivalence:rs121913502",))

    def test_mutating_control_expectation_is_visible(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["negative_controls"][0]["expected_state"] = "absent"
        report = IdentityScenarioMatrix(raw).run()
        self.assertFalse(report.passed)
        self.assertIn("negative:equivalence:out-of-domain-build", report.failed_scenario_ids)

    def test_scenario_results_have_content_addresses(self) -> None:
        report = IdentityScenarioMatrix(self.raw).run()
        for result in report.results:
            self.assertRegex(result.content_address, r"^sha256:[0-9a-f]{64}$")
            self.assertTrue(result.observed_signals)

    def test_injected_evaluator_can_be_reused(self) -> None:
        evaluator = IdentityFixtureEvaluator()
        report = IdentityScenarioMatrix(self.raw, evaluator=evaluator).run()
        self.assertTrue(report.passed)

    def test_report_serializes_counts(self) -> None:
        payload = IdentityScenarioMatrix(self.raw).run().to_dict()
        self.assertEqual(payload["scenario_count"], 12)
        self.assertEqual(payload["passed_count"], 12)
        self.assertTrue(payload["passed"])


if __name__ == "__main__":
    unittest.main()
