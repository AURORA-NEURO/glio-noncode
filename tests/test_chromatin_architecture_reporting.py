"""Reporting and export tests for D07."""

from __future__ import annotations

import csv
import io
import unittest

from glio_noncode.chromatin_architecture_data_dictionary import (
    chromatin_architecture_data_dictionary,
)
from glio_noncode.chromatin_architecture_metrics import materialize_chromatin_architecture_metrics
from glio_noncode.chromatin_architecture_reporting import (
    build_chromatin_architecture_report,
    chromatin_architecture_receipts_csv,
    chromatin_architecture_review_csv,
    render_chromatin_architecture_markdown,
)
from glio_noncode.chromatin_architecture_runtime import run_chromatin_architecture


class ChromatinArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_chromatin_architecture()
        cls.dictionary = chromatin_architecture_data_dictionary(cls.runtime.fixture)
        cls.metrics = materialize_chromatin_architecture_metrics(cls.runtime.evaluation)
        cls.report = build_chromatin_architecture_report(cls.runtime, cls.metrics, cls.dictionary)

    def test_report_counts_and_markdown(self) -> None:
        self.assertTrue(self.report.accepted)
        self.assertEqual(self.report.operation_count, 16)
        self.assertEqual(self.report.source_count, 19)
        self.assertEqual(self.report.stage_count, 24)
        self.assertEqual(self.report.check_count, 458)
        self.assertEqual(self.report.quality_check_count, 14)
        self.assertEqual(self.report.depth_percent, 100.0)
        self.assertTrue(self.report.compliance_accepted)
        markdown = render_chromatin_architecture_markdown(self.report)
        self.assertIn("D07 Chromatin Architecture Report", markdown)
        self.assertIn("methylation_frontier", markdown)

    def test_receipt_and_review_csv_have_expected_rows(self) -> None:
        receipts = list(
            csv.DictReader(io.StringIO(chromatin_architecture_receipts_csv(self.runtime)))
        )
        review = list(csv.DictReader(io.StringIO(chromatin_architecture_review_csv(self.runtime))))
        self.assertEqual(len(receipts), 64)
        self.assertEqual(len(review), 48)
        self.assertEqual(receipts[0]["case_id"], "D07-C01-positive")
        self.assertEqual(review[-1]["case_id"], "D07-C16-identity_conflict")


if __name__ == "__main__":
    unittest.main()
