"""Deterministic reporting and compliance projections for D04."""

from __future__ import annotations

import unittest

from glio_noncode.reference_architecture_compliance import (
    assess_reference_architecture_compliance,
)
from glio_noncode.reference_architecture_metrics import (
    materialize_reference_architecture_metrics,
)
from glio_noncode.reference_architecture_public_data import (
    default_reference_architecture_fixture,
)
from glio_noncode.reference_architecture_reporting import (
    build_reference_architecture_report,
    reference_architecture_receipts_csv,
    reference_architecture_review_csv,
    render_reference_architecture_markdown,
)
from glio_noncode.reference_architecture_runtime import run_reference_architecture
from glio_noncode.reference_architecture_validation import (
    validate_reference_architecture_matrix,
)


class ReferenceArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_reference_architecture_fixture()
        cls.runtime = run_reference_architecture(cls.fixture, run_id="d04-report-test")
        cls.validation = validate_reference_architecture_matrix(
            cls.fixture, cls.runtime.evaluation
        )
        cls.metrics = materialize_reference_architecture_metrics(
            cls.fixture,
            cls.runtime.evaluation,
            cls.runtime.review_queue,
            len(cls.validation),
        )

    def test_compliance_is_public_aggregate_only(self) -> None:
        report = assess_reference_architecture_compliance(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 8)
        self.assertEqual(report.forbidden_key_paths, ())

    def test_report_has_stable_summary_and_sections(self) -> None:
        report = build_reference_architecture_report(
            self.fixture, self.runtime, self.metrics
        )
        self.assertEqual(report.summary["source_count"], 20)
        self.assertEqual(report.summary["evaluation_checks"], 458)
        self.assertEqual(report.summary["depth_percent"], 100.0)
        self.assertEqual(
            tuple(section["section_id"] for section in report.sections),
            ("sources", "operations", "controls", "artifacts"),
        )
        self.assertTrue(report.content_address.startswith("reference-report:"))

    def test_markdown_and_csv_exports_are_bounded(self) -> None:
        report = build_reference_architecture_report(
            self.fixture, self.runtime, self.metrics
        )
        markdown = render_reference_architecture_markdown(report)
        receipts = reference_architecture_receipts_csv(self.runtime)
        reviews = reference_architecture_review_csv(self.runtime.review_queue)
        self.assertIn("D04 Reference Context and Release Architecture", markdown)
        self.assertEqual(len(receipts.splitlines()), 65)
        self.assertEqual(len(reviews.splitlines()), 49)
        self.assertIn("case_id,operation_id", receipts.splitlines()[0])
        self.assertIn("review_id,case_id", reviews.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
