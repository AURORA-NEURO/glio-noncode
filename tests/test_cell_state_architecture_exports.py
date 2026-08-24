"""Public import, JSON projection, and root export tests for D08."""

from __future__ import annotations

import json
import unittest

import glio_noncode
from glio_noncode.cell_state_architecture_normalization import (
    normalize_case_rows,
    review_safe_projection,
)
from glio_noncode.cell_state_architecture_public_data import (
    cell_state_architecture_fixture_json,
    default_cell_state_architecture_fixture,
)


class CellStateArchitectureExportTests(unittest.TestCase):
    def test_root_exports_are_callable(self) -> None:
        for name in (
            "default_cell_state_architecture_fixture",
            "evaluate_cell_state_architecture_fixture",
            "run_cell_state_architecture",
            "validate_cell_state_architecture",
        ):
            self.assertTrue(callable(getattr(glio_noncode, name)))

    def test_fixture_json_has_closed_counts(self) -> None:
        text = cell_state_architecture_fixture_json()
        self.assertGreater(len(text), 50000)
        payload = json.loads(text)
        self.assertEqual(len(payload["sources"]), 18)
        self.assertEqual(len(payload["operations"]), 16)
        self.assertEqual(len(payload["cases"]), 64)
        self.assertTrue(all(item["public_aggregate"] for item in payload["sources"]))
        self.assertTrue(all(item["delegate_context_key"] for item in payload["cases"]))

    def test_review_projection_removes_raw_case_payload(self) -> None:
        fixture = default_cell_state_architecture_fixture()
        projected = review_safe_projection(
            {"payload": {"records": [1]}, "case_id": fixture.cases[0].case_id}
        )
        self.assertEqual(projected, {"case_id": fixture.cases[0].case_id})
        rows = normalize_case_rows(({"z": 1, "a": 2},))
        self.assertEqual(tuple(rows[0]), ("a", "z"))


if __name__ == "__main__":
    unittest.main()
