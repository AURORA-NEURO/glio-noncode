"""Serialization, query, normalization, and public export tests for D04."""

from __future__ import annotations

import unittest

from glio_noncode.reference_architecture_exports import (
    default_reference_architecture_fixture,
    evaluate_reference_architecture_fixture,
    normalize_reference_architecture_mapping,
    reference_architecture_fixture_json,
    reference_cases_for_operation,
    reference_control_case_ids,
    reference_receipts_for_state,
    run_reference_architecture,
    strip_reference_architecture_payloads,
)


class ReferenceArchitectureExportTests(unittest.TestCase):
    def test_fixture_json_is_stable(self) -> None:
        fixture = default_reference_architecture_fixture()
        self.assertEqual(
            reference_architecture_fixture_json(fixture), reference_architecture_fixture_json()
        )
        self.assertIn(
            "reference-architecture-public-aggregate", reference_architecture_fixture_json(fixture)
        )

    def test_queries_are_bounded(self) -> None:
        fixture = default_reference_architecture_fixture()
        evaluation = evaluate_reference_architecture_fixture(fixture)
        self.assertEqual(len(reference_cases_for_operation(fixture, "reference_registry")), 4)
        self.assertEqual(len(reference_control_case_ids(fixture)), 48)
        self.assertEqual(len(reference_receipts_for_state(evaluation, "review")), 48)

    def test_normalization_removes_payloads_only_from_projection(self) -> None:
        fixture = default_reference_architecture_fixture()
        mapping = fixture.cases[0].to_dict()
        normalized = normalize_reference_architecture_mapping(mapping)
        stripped = strip_reference_architecture_payloads(normalized)
        self.assertIn("payload", normalized)
        self.assertNotIn("payload", stripped)
        self.assertEqual(stripped["case_id"], fixture.cases[0].case_id)

    def test_runtime_projection_is_jsonable(self) -> None:
        runtime = run_reference_architecture(run_id="export-test")
        value = runtime.to_dict()
        self.assertTrue(value["accepted"])
        self.assertEqual(value["stage_count"], 20)
        self.assertTrue(value["release"]["published"])


if __name__ == "__main__":
    unittest.main()
