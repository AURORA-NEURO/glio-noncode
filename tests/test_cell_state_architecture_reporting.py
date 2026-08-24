"""Reporting and public registry tests for D08."""

from __future__ import annotations

import json
import unittest

from glio_noncode.cell_state_architecture_reporting import (
    build_cell_state_architecture_report,
    cell_state_architecture_report_json,
    cell_state_architecture_report_lines,
)
from glio_noncode.cell_state_architecture_runbook import (
    cell_state_architecture_runbook,
    cell_state_architecture_stage_runbook,
    module_inventory,
)
from glio_noncode.cell_state_architecture_runtime import run_cell_state_architecture


class CellStateArchitectureReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_cell_state_architecture()
        cls.report = build_cell_state_architecture_report(cls.runtime)

    def test_report_counts_and_lines(self) -> None:
        self.assertTrue(self.report["quality"]["accepted"])
        self.assertEqual(self.report["metrics"]["operation_count"], 16)
        self.assertEqual(self.report["metrics"]["source_count"], 18)
        self.assertEqual(self.report["stage_count"], 24)
        self.assertEqual(self.report["quality"]["check_count"], 12)
        self.assertIn("D08 Cell State", cell_state_architecture_report_lines(self.runtime)[0])

    def test_report_json_and_runbook_are_stable(self) -> None:
        payload = json.loads(cell_state_architecture_report_json(self.runtime))
        self.assertEqual(payload["depth"]["completion_percent"], 100.0)
        self.assertEqual(len(cell_state_architecture_runbook(self.runtime.fixture)), 16)
        self.assertEqual(len(cell_state_architecture_stage_runbook()), 24)
        self.assertGreaterEqual(len(module_inventory()), 29)


if __name__ == "__main__":
    unittest.main()
