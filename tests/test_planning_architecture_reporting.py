"""D13 report, query, dictionary, and projection tests."""

from __future__ import annotations

import unittest

from glio_noncode.planning_architecture_data_dictionary import planning_architecture_data_dictionary
from glio_noncode.planning_architecture_public_data import default_planning_architecture_fixture
from glio_noncode.planning_architecture_query import query_planning_architecture
from glio_noncode.planning_architecture_reporting import (
    build_planning_architecture_report,
    planning_architecture_report_markdown,
)
from glio_noncode.planning_architecture_runtime import run_planning_architecture
from glio_noncode.planning_architecture_views import planning_architecture_case_table


class PlanningArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_planning_architecture_fixture()
        cls.runtime = run_planning_architecture(cls.fixture)

    def test_query_and_sanitized_table(self) -> None:
        result = query_planning_architecture(self.fixture, operation_id="D13-C14")
        self.assertEqual(result.count, 4)
        self.assertTrue(all(item["payload"] == {} for item in result.cases))
        self.assertEqual(len(planning_architecture_case_table(self.fixture)), 64)

    def test_report_and_dictionary(self) -> None:
        report = build_planning_architecture_report(
            self.runtime.fixture,
            self.runtime.evaluation,
            self.runtime,
        )
        markdown = planning_architecture_report_markdown(report)
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["metrics"]["check_count"], 458)
        self.assertIn("D13 Planning Architecture Report", markdown)
        self.assertGreaterEqual(len(planning_architecture_data_dictionary()), 20)


if __name__ == "__main__":
    unittest.main()
