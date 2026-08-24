"""Serialization, query, normalization, and public export tests for D03."""

from __future__ import annotations

import unittest

from glio_noncode.specimen_architecture_exports import (
    cases_for_operation,
    control_case_ids,
    default_specimen_architecture_fixture,
    evaluate_specimen_architecture_fixture,
    normalize_specimen_architecture_mapping,
    receipts_for_state,
    run_specimen_architecture,
    specimen_architecture_fixture_json,
    strip_specimen_architecture_payloads,
)


class SpecimenArchitectureExportTests(unittest.TestCase):
    def test_fixture_json_is_stable(self) -> None:
        fixture = default_specimen_architecture_fixture()
        self.assertEqual(
            specimen_architecture_fixture_json(fixture), specimen_architecture_fixture_json()
        )
        self.assertIn(
            "specimen-architecture-public-aggregate", specimen_architecture_fixture_json(fixture)
        )

    def test_queries_are_bounded(self) -> None:
        fixture = default_specimen_architecture_fixture()
        evaluation = evaluate_specimen_architecture_fixture(fixture)
        self.assertEqual(len(cases_for_operation(fixture, "origin")), 4)
        self.assertEqual(len(control_case_ids(fixture)), 48)
        self.assertEqual(len(receipts_for_state(evaluation, "review")), 48)

    def test_normalization_removes_payloads_only_from_projection(self) -> None:
        fixture = default_specimen_architecture_fixture()
        mapping = fixture.cases[0].to_dict()
        normalized = normalize_specimen_architecture_mapping(mapping)
        stripped = strip_specimen_architecture_payloads(normalized)
        self.assertIn("payload", normalized)
        self.assertNotIn("payload", stripped)
        self.assertEqual(stripped["case_id"], fixture.cases[0].case_id)

    def test_runtime_projection_is_jsonable(self) -> None:
        runtime = run_specimen_architecture(run_id="export-test")
        value = runtime.to_dict()
        self.assertTrue(value["accepted"])
        self.assertEqual(value["stage_count"], 24)
        self.assertEqual(value["release"]["published"], True)
        self.assertEqual(value["depth"]["check_count"], 458)
        self.assertTrue(value["compliance"]["accepted"])


if __name__ == "__main__":
    unittest.main()
