"""Public import and JSON projection tests for D09."""

from __future__ import annotations

import json
import unittest

import glio_noncode
from glio_noncode.topology_architecture_public_data import (
    default_topology_architecture_fixture,
    topology_architecture_fixture_json,
)
from glio_noncode.topology_architecture_views import topology_architecture_case_views


class TopologyArchitectureExportTests(unittest.TestCase):
    def test_root_exports_are_callable(self) -> None:
        for name in (
            "default_topology_architecture_fixture",
            "evaluate_topology_architecture_fixture",
            "run_topology_architecture",
            "validate_topology_architecture_fixture",
        ):
            self.assertTrue(callable(getattr(glio_noncode, name)))

    def test_fixture_json_has_closed_counts(self) -> None:
        text = topology_architecture_fixture_json()
        self.assertGreater(len(text), 50000)
        payload = json.loads(text)
        self.assertEqual(len(payload["sources"]), 17)
        self.assertEqual(len(payload["operations"]), 16)
        self.assertEqual(len(payload["cases"]), 64)

    def test_case_views_keep_all_receipts_and_addresses(self) -> None:
        runtime = glio_noncode.run_topology_architecture(default_topology_architecture_fixture())
        rows = topology_architecture_case_views(runtime)
        self.assertEqual(len(rows), 64)
        self.assertTrue(all(row["output_address"].startswith("sha256:") for row in rows))
        self.assertEqual(sum(row["scenario"] == "positive" for row in rows), 16)


if __name__ == "__main__":
    unittest.main()
