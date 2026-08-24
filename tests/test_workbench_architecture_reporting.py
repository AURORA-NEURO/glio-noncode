"""D15 report, query, dictionary, and projection tests."""

from __future__ import annotations

import unittest

from glio_noncode.workbench_architecture_data_dictionary import (
    workbench_architecture_data_dictionary,
)
from glio_noncode.workbench_architecture_public_data import default_workbench_architecture_fixture
from glio_noncode.workbench_architecture_query import query_workbench_architecture
from glio_noncode.workbench_architecture_reporting import (
    build_workbench_architecture_report,
    workbench_architecture_report_markdown,
)
from glio_noncode.workbench_architecture_runtime import run_workbench_architecture
from glio_noncode.workbench_architecture_views import workbench_architecture_case_view


class WorkbenchArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_workbench_architecture_fixture()
        cls.runtime = run_workbench_architecture(cls.fixture)

    def test_query_and_case_view(self) -> None:
        rows = query_workbench_architecture(
            fixture=self.fixture, evaluation=self.runtime.evaluation, operation="D15-C14"
        )
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(workbench_architecture_case_view(self.runtime.evaluation)), 64)
        self.assertTrue(all(item["output_address"] for item in rows))

    def test_report_and_dictionary(self) -> None:
        report = build_workbench_architecture_report(
            self.runtime.fixture, self.runtime.evaluation, self.runtime
        )
        markdown = workbench_architecture_report_markdown(report)
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["metrics"]["check_count"], 458)
        self.assertIn("D15 Workbench Architecture Report", markdown)
        self.assertGreaterEqual(len(workbench_architecture_data_dictionary()), 13)


if __name__ == "__main__":
    unittest.main()
