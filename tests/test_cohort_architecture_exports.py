"""Public D12 import and fixture projection tests."""

from __future__ import annotations

import json
import unittest

import glio_noncode
from glio_noncode.cohort_architecture_public_data import (
    cohort_architecture_fixture_json,
    default_cohort_architecture_fixture,
)
from glio_noncode.cohort_architecture_views import cohort_architecture_case_views


class CohortArchitectureExportTests(unittest.TestCase):
    def test_root_exports_are_callable(self) -> None:
        for name in (
            "default_cohort_architecture_fixture",
            "evaluate_cohort_architecture_fixture",
            "run_cohort_architecture",
            "validate_cohort_architecture_fixture",
        ):
            self.assertTrue(callable(getattr(glio_noncode, name)))

    def test_fixture_json_has_closed_counts(self) -> None:
        text = cohort_architecture_fixture_json()
        self.assertGreater(len(text), 80000)
        payload = json.loads(text)
        self.assertEqual(len(payload["sources"]), 22)
        self.assertEqual(len(payload["operations"]), 16)
        self.assertEqual(len(payload["cases"]), 64)

    def test_case_views_keep_context_and_addresses(self) -> None:
        runtime = glio_noncode.run_cohort_architecture(default_cohort_architecture_fixture())
        rows = cohort_architecture_case_views(runtime)
        self.assertEqual(len(rows), 64)
        self.assertEqual(sum(row["scenario"] == "positive" for row in rows), 16)
        self.assertTrue(all(row["delegate_context_key"] for row in rows))
        self.assertTrue(all(row["output_address"] for row in rows))


if __name__ == "__main__":
    unittest.main()
