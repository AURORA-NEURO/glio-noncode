"""Data dictionary and release-report tests for D06."""

from __future__ import annotations

import unittest

from glio_noncode.sequence_architecture_compliance import assess_sequence_architecture_compliance
from glio_noncode.sequence_architecture_data_dictionary import sequence_architecture_data_dictionary
from glio_noncode.sequence_architecture_metrics import materialize_sequence_architecture_metrics
from glio_noncode.sequence_architecture_operations import evaluate_sequence_architecture_fixture
from glio_noncode.sequence_architecture_public_data import default_sequence_architecture_fixture
from glio_noncode.sequence_architecture_reporting import (
    build_sequence_architecture_report,
    render_sequence_architecture_markdown,
    sequence_architecture_receipts_csv,
    sequence_architecture_review_csv,
)
from glio_noncode.sequence_architecture_runtime import run_sequence_architecture
from glio_noncode.sequence_architecture_source_registry import (
    build_sequence_architecture_source_registry,
    sequence_source_binding_for,
)
from glio_noncode.sequence_architecture_validation import validate_sequence_architecture_matrix


class SequenceArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_sequence_architecture_fixture()
        cls.runtime = run_sequence_architecture(cls.fixture, run_id="reporting-sequence-runtime")

    def test_dictionary_covers_every_persisted_entity(self) -> None:
        dictionary = sequence_architecture_data_dictionary(self.fixture)
        self.assertTrue(dictionary.accepted)
        self.assertEqual(len(dictionary.fields), 30)
        self.assertEqual(len(dictionary.checks), 6)
        self.assertEqual(
            {item.entity for item in dictionary.fields},
            {"source", "operation", "case", "receipt", "review", "ledger", "artifact"},
        )
        self.assertTrue(all(item.privacy == "public_aggregate" for item in dictionary.fields))

    def test_report_markdown_and_csv_are_stable(self) -> None:
        evaluation = evaluate_sequence_architecture_fixture(self.fixture)
        validation = validate_sequence_architecture_matrix(self.fixture, evaluation)
        metrics = materialize_sequence_architecture_metrics(
            self.fixture, evaluation, self.runtime.review_queue, len(validation)
        )
        report = build_sequence_architecture_report(
            self.fixture,
            self.runtime,
            metrics,
            sequence_architecture_data_dictionary(self.fixture),
        )
        markdown = render_sequence_architecture_markdown(report)
        self.assertIn("D06 Sequence Grammar and Variant Effect Architecture", markdown)
        self.assertIn("Public sequence sources", markdown)
        self.assertEqual(markdown, render_sequence_architecture_markdown(report))
        receipts = sequence_architecture_receipts_csv(self.runtime)
        reviews = sequence_architecture_review_csv(self.runtime.review_queue)
        self.assertEqual(len(receipts.splitlines()), 65)
        self.assertEqual(len(reviews.splitlines()), 49)
        self.assertIn("case_id,operation_id", receipts)
        self.assertIn("review_id,case_id", reviews)

    def test_compliance_and_source_registry_close_public_scope(self) -> None:
        compliance = assess_sequence_architecture_compliance(self.fixture)
        self.assertTrue(compliance.accepted)
        self.assertEqual(compliance.forbidden_key_paths, ())
        registry = build_sequence_architecture_source_registry(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.bindings), 17)
        binding = sequence_source_binding_for(registry, self.fixture.sources[0].source_id)
        self.assertGreater(binding.case_count, 0)
        with self.assertRaises(KeyError):
            sequence_source_binding_for(registry, "missing-d06-source")


if __name__ == "__main__":
    unittest.main()
