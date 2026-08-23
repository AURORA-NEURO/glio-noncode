"""Reporting, source registry, data dictionary, and scenario coverage for D05."""

from __future__ import annotations

import unittest

from glio_noncode.atlas_architecture_data_dictionary import atlas_architecture_data_dictionary
from glio_noncode.atlas_architecture_metrics import materialize_atlas_architecture_metrics
from glio_noncode.atlas_architecture_public_data import default_atlas_architecture_fixture
from glio_noncode.atlas_architecture_reporting import (
    atlas_architecture_receipts_csv,
    atlas_architecture_review_csv,
    atlas_architecture_sources_csv,
    build_atlas_architecture_report,
    render_atlas_architecture_markdown,
)
from glio_noncode.atlas_architecture_runtime import run_atlas_architecture
from glio_noncode.atlas_architecture_scenarios import (
    atlas_architecture_scenario_summary,
    build_atlas_architecture_scenario_matrix,
)
from glio_noncode.atlas_architecture_source_registry import (
    build_atlas_architecture_source_registry,
    source_binding_for,
)
from glio_noncode.atlas_architecture_validation import validate_atlas_architecture_matrix


class AtlasArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_atlas_architecture_fixture()
        cls.runtime = run_atlas_architecture(cls.fixture, run_id="reporting-runtime")

    def test_dictionary_is_complete_and_public(self) -> None:
        dictionary = atlas_architecture_data_dictionary(self.fixture)
        self.assertTrue(dictionary.accepted)
        self.assertEqual(len(dictionary.fields), 31)
        self.assertEqual(len(dictionary.checks), 6)
        self.assertEqual(
            {item.entity for item in dictionary.fields},
            {"source", "operation", "case", "receipt", "review", "ledger", "artifact"},
        )
        self.assertTrue(all(item.privacy == "public_aggregate" for item in dictionary.fields))
        self.assertTrue(
            all(item.content_address.startswith("sha256:") for item in dictionary.fields)
        )

    def test_source_registry_closes_public_provenance(self) -> None:
        registry = build_atlas_architecture_source_registry(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.bindings), 20)
        self.assertTrue(all(item.operation_ids for item in registry.bindings))
        binding = source_binding_for(registry, self.fixture.sources[0].source_id)
        self.assertGreaterEqual(binding.case_count, 1)
        with self.assertRaises(KeyError):
            source_binding_for(registry, "not-in-d05")

    def test_scenario_matrix_has_balanced_controls(self) -> None:
        matrix = build_atlas_architecture_scenario_matrix(self.fixture, self.runtime.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.rows), 64)
        self.assertEqual(len(matrix.checks), 8)
        summary = atlas_architecture_scenario_summary(matrix)
        self.assertEqual(
            summary["scenario_counts"],
            {"positive": 16, "foreign_context": 16, "malformed_input": 16, "identity_conflict": 16},
        )
        self.assertEqual(summary["observed_state_counts"], {"accepted": 16, "review": 48})
        self.assertEqual(summary["failed_rows"], [])

    def test_report_and_csv_exports_are_deterministic(self) -> None:
        validation = validate_atlas_architecture_matrix(self.fixture, self.runtime.evaluation)
        metrics = materialize_atlas_architecture_metrics(
            self.fixture,
            self.runtime.evaluation,
            self.runtime.review_queue,
            len(validation),
        )
        report = build_atlas_architecture_report(
            self.fixture,
            self.runtime,
            metrics,
            atlas_architecture_data_dictionary(self.fixture),
        )
        markdown = render_atlas_architecture_markdown(report)
        self.assertIn("D05 Glioma Regulatory Atlas Architecture", markdown)
        self.assertIn("Public provenance", markdown)
        self.assertEqual(markdown, render_atlas_architecture_markdown(report))
        receipts = atlas_architecture_receipts_csv(self.runtime)
        review = atlas_architecture_review_csv(self.runtime.review_queue)
        sources = atlas_architecture_sources_csv(self.fixture)
        self.assertEqual(len(receipts.splitlines()), 65)
        self.assertEqual(len(review.splitlines()), 49)
        self.assertEqual(len(sources.splitlines()), 21)
        self.assertIn("case_id,operation_id", receipts)
        self.assertIn("review_id,case_id", review)
        self.assertIn("source_id,family", sources)


if __name__ == "__main__":
    unittest.main()
