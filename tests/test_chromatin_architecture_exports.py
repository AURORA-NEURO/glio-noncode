"""Public import and projection tests for D07."""

from __future__ import annotations

import json
import unittest

import glio_noncode
from glio_noncode.chromatin_architecture_contracts import ChromatinArchitectureOperation
from glio_noncode.chromatin_architecture_normalization import (
    chromatin_architecture_public_projection,
    normalize_chromatin_architecture_mapping,
)
from glio_noncode.chromatin_architecture_operations import evaluate_chromatin_architecture_fixture
from glio_noncode.chromatin_architecture_public_data import (
    chromatin_architecture_fixture_json,
    default_chromatin_architecture_fixture,
)
from glio_noncode.chromatin_architecture_query import (
    ChromatinArchitectureQuery,
    query_chromatin_architecture,
)


class ChromatinArchitectureExportTests(unittest.TestCase):
    def test_root_exports_are_callable(self) -> None:
        for name in (
            "default_chromatin_architecture_fixture",
            "evaluate_chromatin_architecture_fixture",
            "run_chromatin_architecture",
            "chromatin_architecture_schema",
            "validate_chromatin_architecture_matrix",
            "assess_chromatin_architecture_compliance",
        ):
            self.assertTrue(callable(getattr(glio_noncode, name)))

    def test_fixture_json_is_large_and_round_trippable(self) -> None:
        text = chromatin_architecture_fixture_json()
        self.assertGreater(len(text), 50000)
        payload = json.loads(text)
        self.assertEqual(len(payload["sources"]), 19)
        self.assertEqual(len(payload["operations"]), 16)
        self.assertEqual(len(payload["cases"]), 64)

    def test_query_and_projection_are_stable(self) -> None:
        fixture = default_chromatin_architecture_fixture()
        evaluation = evaluate_chromatin_architecture_fixture(fixture)
        result = query_chromatin_architecture(
            fixture.cases,
            evaluation,
            ChromatinArchitectureQuery(
                operation=ChromatinArchitectureOperation.METHYLATION_CONTEXT
            ),
        )
        self.assertEqual(result.matched_count, 4)
        mapping = normalize_chromatin_architecture_mapping({"z": 1.2345678912345, "a": {"b": 2}})
        self.assertEqual(tuple(mapping), ("a", "z"))
        projected = chromatin_architecture_public_projection(
            {"payload": {"raw": True}, "case_id": "D07-C01-positive"}
        )
        self.assertEqual(projected, {"case_id": "D07-C01-positive"})


if __name__ == "__main__":
    unittest.main()
