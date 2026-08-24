"""Deterministic reporting and compliance projections for D03."""

from __future__ import annotations

import unittest

from glio_noncode.specimen_architecture_compliance import (
    assess_specimen_architecture_compliance,
)
from glio_noncode.specimen_architecture_metrics import (
    materialize_specimen_architecture_metrics,
)
from glio_noncode.specimen_architecture_public_data import (
    default_specimen_architecture_fixture,
)
from glio_noncode.specimen_architecture_reporting import (
    build_specimen_architecture_report,
    render_specimen_architecture_markdown,
    specimen_architecture_receipts_csv,
    specimen_architecture_review_csv,
)
from glio_noncode.specimen_architecture_runtime import run_specimen_architecture
from glio_noncode.specimen_architecture_validation import (
    validate_specimen_architecture_matrix,
)


class SpecimenArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_specimen_architecture_fixture()
        cls.runtime = run_specimen_architecture(cls.fixture, run_id="d03-report-test")
        validation = validate_specimen_architecture_matrix(
            cls.fixture, cls.runtime.evaluation
        )
        cls.metrics = materialize_specimen_architecture_metrics(
            cls.fixture,
            cls.runtime.evaluation,
            cls.runtime.review_queue,
            len(validation),
        )

    def test_compliance_is_public_aggregate_only(self) -> None:
        report = assess_specimen_architecture_compliance(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 8)
        self.assertEqual(report.forbidden_key_paths, ())

    def test_report_has_stable_summary_and_sections(self) -> None:
        report = build_specimen_architecture_report(
            self.fixture, self.runtime, self.metrics
        )
        self.assertEqual(report.summary["source_count"], 15)
        self.assertEqual(report.summary["evaluation_checks"], 458)
        self.assertEqual(report.summary["depth_percent"], 100.0)
        self.assertEqual(
            tuple(section["section_id"] for section in report.sections),
            ("sources", "operations", "controls", "artifacts"),
        )
        self.assertTrue(report.content_address.startswith("specimen-report:"))

    def test_markdown_and_csv_exports_are_bounded(self) -> None:
        report = build_specimen_architecture_report(
            self.fixture, self.runtime, self.metrics
        )
        markdown = render_specimen_architecture_markdown(report)
        receipts = specimen_architecture_receipts_csv(self.runtime)
        reviews = specimen_architecture_review_csv(self.runtime.review_queue)
        self.assertIn("D03 Specimen Context and Release Architecture", markdown)
        self.assertEqual(len(receipts.splitlines()), 65)
        self.assertEqual(len(reviews.splitlines()), 49)
        self.assertIn("case_id,operation_id", receipts.splitlines()[0])
        self.assertIn("review_id,case_id", reviews.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
