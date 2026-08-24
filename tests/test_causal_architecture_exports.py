"""Public D11 import and fixture projection tests."""

from __future__ import annotations

import json
import unittest

import glio_noncode
from glio_noncode.causal_architecture_public_data import (
    causal_architecture_fixture_json,
    default_causal_architecture_fixture,
)
from glio_noncode.causal_architecture_views import causal_architecture_case_views


class CausalArchitectureExportTests(unittest.TestCase):
    def test_root_exports_are_callable(self) -> None:
        for name in (
            "default_causal_architecture_fixture",
            "evaluate_causal_architecture_fixture",
            "run_causal_architecture",
            "validate_causal_architecture_fixture",
        ):
            self.assertTrue(callable(getattr(glio_noncode, name)))

    def test_fixture_json_has_closed_counts(self) -> None:
        text = causal_architecture_fixture_json()
        self.assertGreater(len(text), 50000)
        payload = json.loads(text)
        self.assertEqual(len(payload["sources"]), 20)
        self.assertEqual(len(payload["operations"]), 16)
        self.assertEqual(len(payload["cases"]), 64)

    def test_case_views_keep_delegate_context_and_addresses(self) -> None:
        runtime = glio_noncode.run_causal_architecture(default_causal_architecture_fixture())
        rows = causal_architecture_case_views(runtime)
        self.assertEqual(len(rows), 64)
        self.assertEqual(sum(row["scenario"] == "positive" for row in rows), 16)
        self.assertTrue(all(row["output_address"].startswith("sha256:") for row in rows))


if __name__ == "__main__":
    unittest.main()
