"""CLI smoke tests for planning commands."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PlanningCliTests(unittest.TestCase):
    def run_cli(self, command: str) -> tuple[int, dict | str]:
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "output.json"
            completed = subprocess.run([sys.executable, "-m", "glio_noncode", command, "--output", str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            text = output.read_text(encoding="utf-8")
            try:
                return completed.returncode, json.loads(text)
            except json.JSONDecodeError:
                return completed.returncode, text

    def test_pipeline(self) -> None:
        _, value = self.run_cli("planning-frontier-pipeline")
        self.assertTrue(value["accepted"])
        self.assertGreaterEqual(len(value["stages"]), 28)

    def test_data_audit_and_depth(self) -> None:
        _, audit = self.run_cli("planning-frontier-data-audit")
        _, depth = self.run_cli("planning-frontier-depth")
        self.assertTrue(audit["accepted"])
        self.assertTrue(depth["accepted"])

    def test_report_and_csv(self) -> None:
        _, report = self.run_cli("planning-frontier-report")
        self.assertIn("D13 C09-C12", report)
        _, csv_text = self.run_cli("planning-frontier-review-csv")
        self.assertIn("record_id,operation", csv_text)


if __name__ == "__main__":
    unittest.main()
