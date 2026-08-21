from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_scenario_matrix import (
    FrontierScenario,
    FrontierScenarioMatrix,
    ScenarioExpectation,
    evaluate_frontier_scenarios,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "frontier-glioma-case.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class FrontierScenarioMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.matrix = FrontierScenarioMatrix(self.fixture)

    def test_fixture_matrix_has_four_positive_and_four_negative_scenarios(self) -> None:
        scenarios = self.matrix.scenarios()
        self.assertEqual(len(scenarios), 8)
        self.assertEqual(
            tuple(s.scenario_id for s in scenarios[:4]),
            (
                "validation-positive",
                "evidence-positive",
                "workbench-positive",
                "deployment-positive",
            ),
        )
        self.assertEqual(
            tuple(s.expected_state for s in scenarios[:4]),
            (ScenarioExpectation.ACCEPTED,) * 4,
        )
        self.assertEqual(
            tuple(s.expected_state for s in scenarios[4:]),
            (ScenarioExpectation.REVIEW,) * 4,
        )

    def test_matrix_context_key_is_derived_from_six_context_dimensions(self) -> None:
        self.assertEqual(self.matrix.context_key, CONTEXT)

    def test_positive_payloads_receive_stable_matrix_pipeline_ids(self) -> None:
        scenarios = self.matrix.scenarios()
        positive = scenarios[:4]
        self.assertEqual(
            tuple(s.payload["pipeline_id"] for s in positive),
            (
                "fixture-matrix:validation",
                "fixture-matrix:evidence",
                "fixture-matrix:workbench",
                "fixture-matrix:deployment",
            ),
        )

    def test_negative_controls_preserve_declared_blocked_stages(self) -> None:
        scenarios = self.matrix.scenarios()[4:]
        self.assertEqual(
            scenarios[0].expected_blocked_stage_ids,
            ("off_target_risk",),
        )
        self.assertEqual(
            scenarios[1].expected_blocked_stage_ids,
            ("graph_integrity",),
        )
        self.assertEqual(
            scenarios[2].expected_blocked_stage_ids,
            ("accessibility",),
        )
        self.assertEqual(
            scenarios[3].expected_blocked_stage_ids,
            ("security_policy",),
        )

    def test_fixture_matrix_passes_all_state_transitions(self) -> None:
        report = self.matrix.run()
        self.assertTrue(report.passed)
        self.assertEqual(report.state, FrontierState.ACCEPTED)
        self.assertEqual(len(report.results), 8)
        self.assertEqual(report.failed_scenario_ids, ())
        self.assertEqual(
            report.accepted_scenario_ids,
            (
                "validation-positive",
                "evidence-positive",
                "workbench-positive",
                "deployment-positive",
            ),
        )
        self.assertEqual(
            report.review_scenario_ids,
            (
                "negative:validation-context-mismatch",
                "negative:evidence-cycle-review",
                "negative:workbench-accessibility-review",
                "negative:deployment-policy-review",
            ),
        )

    def test_each_result_has_its_own_content_address(self) -> None:
        report = self.matrix.run()
        addresses = tuple(result.content_address for result in report.results)
        self.assertEqual(len(set(addresses)), len(addresses))
        for address in addresses:
            self.assertRegex(address, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_matrix_serialization_includes_counts_and_verdict(self) -> None:
        payload = self.matrix.run().to_dict()
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["scenario_count"], 8)
        self.assertEqual(payload["state"], "accepted")
        self.assertEqual(len(payload["results"]), 8)
        self.assertTrue(all("passed" in result for result in payload["results"]))

    def test_convenience_function_matches_file_runner(self) -> None:
        expected = FrontierScenarioMatrix.from_file(FIXTURE).run().to_dict()
        actual = evaluate_frontier_scenarios(FIXTURE).to_dict()
        self.assertEqual(actual, expected)

    def test_matrix_is_deterministic_across_runs(self) -> None:
        first = evaluate_frontier_scenarios(FIXTURE).to_dict()
        second = evaluate_frontier_scenarios(FIXTURE).to_dict()
        self.assertEqual(first, second)

    def test_deepcopy_fixture_does_not_change_matrix(self) -> None:
        first = FrontierScenarioMatrix(self.fixture).run().to_dict()
        second = FrontierScenarioMatrix(copy.deepcopy(self.fixture)).run().to_dict()
        self.assertEqual(first, second)

    def test_invalid_fixture_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                FrontierScenarioMatrix.from_file(path)

    def test_missing_context_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture.pop("context")
        with self.assertRaises(ValidationError):
            FrontierScenarioMatrix(fixture)

    def test_non_object_context_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["context"] = []
        with self.assertRaises(ValidationError):
            FrontierScenarioMatrix(fixture)

    def test_missing_pipeline_container_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture.pop("pipelines")
        matrix = FrontierScenarioMatrix(fixture)
        with self.assertRaises(ValidationError):
            matrix.scenarios()

    def test_missing_negative_control_payload_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"][0].pop("payload")
        matrix = FrontierScenarioMatrix(fixture)
        with self.assertRaises(ValidationError):
            matrix.scenarios()

    def test_missing_negative_control_operation_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"][0].pop("operation")
        matrix = FrontierScenarioMatrix(fixture)
        with self.assertRaises(ValidationError):
            matrix.scenarios()

    def test_mutated_positive_payload_changes_matrix_state_and_fails(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["pipelines"]["validation"]["risk_records"][0]["context_key"] = "wrong-context"
        report = FrontierScenarioMatrix(fixture).run()
        self.assertFalse(report.passed)
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("validation-positive", report.failed_scenario_ids)
        validation = report.results[0]
        self.assertEqual(validation.expected_state, "accepted")
        self.assertEqual(validation.observed_state, "review")

    def test_mutated_negative_payload_remains_review_when_control_is_stricter(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["negative_controls"][3]["payload"]["requests"][0]["network"] = False
        report = FrontierScenarioMatrix(fixture).run()
        self.assertTrue(report.passed)
        self.assertEqual(report.results[-1].observed_state, "review")

    def test_scenario_requires_non_empty_identifier(self) -> None:
        with self.assertRaises(ValidationError):
            FrontierScenario(
                " ",
                "run-validation-frontier-pipeline",
                ScenarioExpectation.ACCEPTED,
                {},
            )

    def test_scenario_requires_non_empty_operation(self) -> None:
        with self.assertRaises(ValidationError):
            FrontierScenario("scenario", " ", ScenarioExpectation.ACCEPTED, {})

    def test_scenario_requires_mapping_payload(self) -> None:
        with self.assertRaises(ValidationError):
            FrontierScenario("scenario", "operation", ScenarioExpectation.ACCEPTED, [])

    def test_scenario_to_dict_is_json_ready(self) -> None:
        scenario = self.matrix.scenarios()[0]
        payload = scenario.to_dict()
        self.assertEqual(payload["scenario_id"], "validation-positive")
        self.assertEqual(payload["expected_state"], "accepted")
        self.assertIsInstance(payload["payload"], dict)

    def test_all_declared_negative_controls_are_reviewed(self) -> None:
        report = self.matrix.run()
        for result in report.results[4:]:
            self.assertEqual(result.expected_state, "review")
            self.assertEqual(result.observed_state, "review")
            self.assertTrue(result.expected_blocked_stage_ids)
            self.assertTrue(
                set(result.expected_blocked_stage_ids).issubset(
                    set(result.observed_blocked_stage_ids)
                )
            )

    def test_matrix_reports_only_failed_scenarios(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["pipelines"]["deployment"]["requests"][0]["network"] = True
        report = FrontierScenarioMatrix(fixture).run()
        self.assertFalse(report.passed)
        self.assertEqual(report.failed_scenario_ids, ("deployment-positive",))

    def test_matrix_result_state_strings_are_contract_values(self) -> None:
        report = self.matrix.run()
        for result in report.results:
            self.assertIn(result.expected_state, {"accepted", "review"})
            self.assertIn(result.observed_state, {"accepted", "review"})


if __name__ == "__main__":
    unittest.main()
