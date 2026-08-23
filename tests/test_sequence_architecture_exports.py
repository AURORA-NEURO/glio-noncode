"""Public export, scenario, and payload-normalization coverage for D06."""

from __future__ import annotations

import unittest

from glio_noncode.sequence_architecture_exports import (
    build_sequence_architecture_scenario_matrix,
    normalize_sequence_architecture_mapping,
    replay_sequence_architecture_fixture,
    run_sequence_architecture,
    sequence_architecture_fixture_json,
    sequence_architecture_scenario_summary,
    sequence_cases_for_operation,
    sequence_control_case_ids,
    sequence_receipts_for_state,
    strip_sequence_architecture_payloads,
)
from glio_noncode.sequence_architecture_operations import evaluate_sequence_architecture_fixture
from glio_noncode.sequence_architecture_public_data import default_sequence_architecture_fixture


class SequenceArchitectureExportTests(unittest.TestCase):
    def test_fixture_query_and_normalization_exports(self) -> None:
        fixture = default_sequence_architecture_fixture()
        payload = sequence_architecture_fixture_json(fixture)
        self.assertEqual(payload, sequence_architecture_fixture_json(fixture))
        self.assertGreater(len(payload), 50000)
        self.assertEqual(len(sequence_cases_for_operation(fixture, "context_encoding")), 4)
        self.assertEqual(len(sequence_control_case_ids(fixture)), 48)
        evaluation = evaluate_sequence_architecture_fixture(fixture)
        self.assertEqual(len(sequence_receipts_for_state(evaluation, "review")), 48)
        normalized = normalize_sequence_architecture_mapping({"fixture": {"payload": {"x": 1}}})
        self.assertEqual(normalized["fixture"]["payload"]["x"], 1)
        stripped = strip_sequence_architecture_payloads(
            {"cases": [{"payload": {"x": 1}, "input_text": "hidden"}]}
        )
        self.assertNotIn("payload", stripped["cases"][0])
        self.assertNotIn("input_text", stripped["cases"][0])

    def test_scenario_and_runtime_exports(self) -> None:
        fixture = default_sequence_architecture_fixture()
        runtime = run_sequence_architecture(fixture, run_id="export-sequence-runtime")
        matrix = build_sequence_architecture_scenario_matrix(fixture, runtime.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.rows), 64)
        summary = sequence_architecture_scenario_summary(matrix)
        self.assertEqual(summary["scenario_counts"]["positive"], 16)
        self.assertEqual(summary["scenario_counts"]["identity_conflict"], 16)
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.to_dict()["stage_count"], 20)
        self.assertEqual(runtime.to_dict()["release"]["state"], "published")
        self.assertTrue(replay_sequence_architecture_fixture(fixture, runtime.evaluation).accepted)


if __name__ == "__main__":
    unittest.main()
