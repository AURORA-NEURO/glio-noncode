"""D11 report, runbook, dictionary, and release projection tests."""

from __future__ import annotations

import json
import unittest

from glio_noncode.causal_architecture_data_dictionary import causal_architecture_data_dictionary
from glio_noncode.causal_architecture_reporting import (
    build_causal_architecture_report,
    causal_architecture_report_json,
    causal_architecture_report_lines,
)
from glio_noncode.causal_architecture_runbook import (
    causal_architecture_module_inventory,
    causal_architecture_runbook,
    causal_architecture_stage_runbook,
)
from glio_noncode.causal_architecture_runtime import run_causal_architecture


class CausalArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_causal_architecture()

    def test_report_is_addressed_and_complete(self) -> None:
        report = build_causal_architecture_report(self.runtime)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["depth"]["completion_percent"], 100.0)
        self.assertTrue(report["content_address"].startswith("sha256:"))
        lineage = json.loads(causal_architecture_report_json(self.runtime))["lineage"]
        self.assertEqual(sum(len(value) for value in lineage["operation_cases"].values()), 64)

    def test_report_lines_runbook_and_dictionary(self) -> None:
        self.assertEqual(len(causal_architecture_report_lines(self.runtime)), 5)
        self.assertEqual(len(causal_architecture_runbook(self.runtime.fixture)), 16)
        self.assertEqual(len(causal_architecture_stage_runbook()), 22)
        self.assertEqual(len(causal_architecture_module_inventory()), 25)
        self.assertIn("fixture", causal_architecture_data_dictionary())


if __name__ == "__main__":
    unittest.main()
