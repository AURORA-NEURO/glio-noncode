"""D16 report and query projection tests."""

from __future__ import annotations

import unittest

from glio_noncode.platform_execution_architecture_public_data import (
    default_platform_execution_fixture,
)
from glio_noncode.platform_execution_architecture_query import query_platform_execution
from glio_noncode.platform_execution_architecture_reporting import (
    build_platform_execution_report,
    platform_execution_report_markdown,
)
from glio_noncode.platform_execution_architecture_runtime import run_platform_execution_architecture


class PlatformExecutionArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_platform_execution_fixture()
        cls.runtime = run_platform_execution_architecture(cls.fixture)

    def test_query_projection(self) -> None:
        rows = query_platform_execution(
            fixture=self.fixture,
            evaluation=self.runtime.evaluation,
            operation="D16-C14",
        )
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(item["output_address"] for item in rows))

    def test_report_projection(self) -> None:
        report = build_platform_execution_report(
            self.runtime.fixture,
            self.runtime.evaluation,
            self.runtime,
        )
        markdown = platform_execution_report_markdown(report)
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["metrics"]["check_count"], 458)
        self.assertIn("D16 Platform Execution Architecture Report", markdown)
        self.assertGreaterEqual(len(report["operations"]), 16)


if __name__ == "__main__":
    unittest.main()
