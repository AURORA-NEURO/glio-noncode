"""Public export and sanitized query coverage for D05."""

from __future__ import annotations

import unittest

from glio_noncode.atlas_architecture_exports import (
    atlas_architecture_fixture_json,
    atlas_cases_for_operation,
    atlas_control_case_ids,
    atlas_receipts_for_state,
    normalize_atlas_architecture_mapping,
    replay_atlas_architecture_fixture,
    run_atlas_architecture,
    strip_atlas_architecture_payloads,
)
from glio_noncode.atlas_architecture_operations import evaluate_atlas_architecture_fixture
from glio_noncode.atlas_architecture_public_data import default_atlas_architecture_fixture


class AtlasArchitectureExportTests(unittest.TestCase):
    def test_fixture_query_and_normalization_exports(self) -> None:
        fixture = default_atlas_architecture_fixture()
        payload = atlas_architecture_fixture_json(fixture)
        self.assertEqual(payload, atlas_architecture_fixture_json(fixture))
        self.assertEqual(len(atlas_cases_for_operation(fixture, "ccre_track_parse")), 4)
        self.assertEqual(len(atlas_control_case_ids(fixture)), 48)
        evaluation = evaluate_atlas_architecture_fixture(fixture)
        self.assertEqual(len(atlas_receipts_for_state(evaluation, "review")), 48)
        normalized = normalize_atlas_architecture_mapping({"fixture": {"payload": {"x": 1}}})
        self.assertEqual(normalized["fixture"]["payload"]["x"], 1)
        stripped = strip_atlas_architecture_payloads({"cases": [{"payload": {"x": 1}}]})
        self.assertNotIn("payload", stripped["cases"][0])

    def test_runtime_and_replay_exports(self) -> None:
        fixture = default_atlas_architecture_fixture()
        runtime = run_atlas_architecture(fixture, run_id="export-runtime")
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.to_dict()["stage_count"], 24)
        self.assertEqual(runtime.to_dict()["release"]["state"], "published")
        self.assertTrue(replay_atlas_architecture_fixture(fixture, runtime.evaluation).accepted)


if __name__ == "__main__":
    unittest.main()
