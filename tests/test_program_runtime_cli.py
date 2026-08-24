"""CLI verification for the sixteen-domain architecture program surface."""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "glio_noncode", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class ProgramRuntimeCliTests(unittest.TestCase):
    def test_summary_and_runtime_commands(self) -> None:
        summary = run_cli("architecture-program-summary")
        self.assertEqual(summary.returncode, 0, summary.stderr)
        self.assertEqual(json.loads(summary.stdout)["certification_percent"], 100.0)
        runtime = run_cli("architecture-program-runtime")
        self.assertEqual(runtime.returncode, 0, runtime.stderr)
        self.assertEqual(json.loads(runtime.stdout)["stage_count"], 12)

    def test_report_and_csv_commands(self) -> None:
        report = run_cli("architecture-program-report", "--format", "markdown")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("# Architecture program runtime", report.stdout)
        checks = run_cli("architecture-program-checks-csv")
        self.assertEqual(checks.returncode, 0, checks.stderr)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(checks.stdout)))), 172)

    def test_query_and_controls(self) -> None:
        query = run_cli("architecture-program-query", "--domain-id", "D08")
        self.assertEqual(query.returncode, 0, query.stderr)
        self.assertEqual(len(json.loads(query.stdout)["rows"]), 1)
        failures = run_cli("architecture-program-failures")
        self.assertEqual(failures.returncode, 0, failures.stderr)
        self.assertTrue(json.loads(failures.stdout)["accepted"])


if __name__ == "__main__":
    unittest.main()
