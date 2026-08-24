"""Public D10 import and fixture projection tests."""

from __future__ import annotations

import json
import unittest

import glio_noncode
from glio_noncode.link_graph_architecture_public_data import (
    default_link_graph_architecture_fixture,
    link_graph_architecture_fixture_json,
)
from glio_noncode.link_graph_architecture_views import link_graph_architecture_case_views


class LinkGraphArchitectureExportTests(unittest.TestCase):
    def test_root_exports_are_callable(self) -> None:
        for name in (
            "default_link_graph_architecture_fixture",
            "evaluate_link_graph_architecture_fixture",
            "run_link_graph_architecture",
            "validate_link_graph_architecture_fixture",
        ):
            self.assertTrue(callable(getattr(glio_noncode, name)))

    def test_fixture_json_has_closed_counts(self) -> None:
        text = link_graph_architecture_fixture_json()
        self.assertGreater(len(text), 50000)
        payload = json.loads(text)
        self.assertEqual(len(payload["sources"]), 19)
        self.assertEqual(len(payload["operations"]), 16)
        self.assertEqual(len(payload["cases"]), 64)

    def test_case_views_keep_delegate_context_and_addresses(self) -> None:
        runtime = glio_noncode.run_link_graph_architecture(
            default_link_graph_architecture_fixture()
        )
        rows = link_graph_architecture_case_views(runtime)
        self.assertEqual(len(rows), 64)
        self.assertEqual(sum(row["scenario"] == "positive" for row in rows), 16)
        self.assertTrue(all(row["output_address"].startswith("sha256:") for row in rows))


if __name__ == "__main__":
    unittest.main()
