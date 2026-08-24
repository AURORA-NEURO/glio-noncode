"""D14 report, query, dictionary, and projection tests."""

from __future__ import annotations

import unittest

from glio_noncode.evidence_architecture_data_dictionary import evidence_architecture_data_dictionary
from glio_noncode.evidence_architecture_public_data import default_evidence_architecture_fixture
from glio_noncode.evidence_architecture_query import query_evidence_architecture
from glio_noncode.evidence_architecture_reporting import (
    build_evidence_architecture_report,
    evidence_architecture_report_markdown,
)
from glio_noncode.evidence_architecture_runtime import run_evidence_architecture
from glio_noncode.evidence_architecture_views import evidence_architecture_case_view


class EvidenceArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_evidence_architecture_fixture()
        cls.runtime = run_evidence_architecture(cls.fixture)

    def test_query_and_case_view(self) -> None:
        rows = query_evidence_architecture(
            fixture=self.fixture, evaluation=self.runtime.evaluation, operation="D14-C14"
        )
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(evidence_architecture_case_view(self.runtime.evaluation)), 64)
        self.assertTrue(all(item["output_address"] for item in rows))

    def test_report_and_dictionary(self) -> None:
        report = build_evidence_architecture_report(
            self.runtime.fixture, self.runtime.evaluation, self.runtime
        )
        markdown = evidence_architecture_report_markdown(report)
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["metrics"]["check_count"], 458)
        self.assertIn("D14 Evidence Architecture Report", markdown)
        self.assertGreaterEqual(len(evidence_architecture_data_dictionary()), 13)


if __name__ == "__main__":
    unittest.main()
