"""D12 report, runbook, dictionary, and release projections."""

from __future__ import annotations

import json
import unittest

from glio_noncode.cohort_architecture_data_dictionary import cohort_architecture_data_dictionary
from glio_noncode.cohort_architecture_reporting import (
    build_cohort_architecture_report,
    cohort_architecture_report_json,
    cohort_architecture_report_lines,
)
from glio_noncode.cohort_architecture_runbook import (
    cohort_architecture_module_inventory,
    cohort_architecture_runbook,
    cohort_architecture_stage_runbook,
)
from glio_noncode.cohort_architecture_runtime import run_cohort_architecture


class CohortArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_cohort_architecture()

    def test_report_is_addressed_and_complete(self) -> None:
        report = build_cohort_architecture_report(self.runtime)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["depth"]["completion_percent"], 100.0)
        self.assertTrue(report["content_address"].startswith("sha256:"))
        lineage = json.loads(cohort_architecture_report_json(self.runtime))["lineage"]
        self.assertEqual(sum(len(value) for value in lineage["operation_cases"].values()), 64)

    def test_report_lines_runbook_and_dictionary(self) -> None:
        self.assertEqual(len(cohort_architecture_report_lines(self.runtime)), 5)
        self.assertEqual(len(cohort_architecture_runbook(self.runtime.fixture)), 16)
        self.assertEqual(len(cohort_architecture_stage_runbook()), 24)
        self.assertEqual(len(cohort_architecture_module_inventory()), 25)
        self.assertIn("fixture", cohort_architecture_data_dictionary())


if __name__ == "__main__":
    unittest.main()
