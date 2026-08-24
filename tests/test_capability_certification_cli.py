"""CLI verification for live capability certification projections."""

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


class CapabilityCertificationCliTests(unittest.TestCase):
    def test_full_and_summary_commands(self) -> None:
        full = run_cli("capability-certification")
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertEqual(json.loads(full.stdout)["capability_count"], 256)
        summary = run_cli("capability-certification-summary")
        self.assertEqual(summary.returncode, 0, summary.stderr)
        self.assertEqual(json.loads(summary.stdout)["certification_percent"], 100.0)

    def test_runtime_and_report_commands(self) -> None:
        runtime = run_cli("capability-certification-runtime")
        self.assertEqual(runtime.returncode, 0, runtime.stderr)
        self.assertEqual(json.loads(runtime.stdout)["stage_count"], 12)
        report = run_cli("capability-certification-report", "--format", "markdown")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("# Capability certification", report.stdout)

    def test_csv_and_query_commands(self) -> None:
        rows = run_cli("capability-certification-csv")
        self.assertEqual(rows.returncode, 0, rows.stderr)
        self.assertEqual(len(rows.stdout.splitlines()), 257)
        checks = run_cli("capability-certification-checks-csv")
        self.assertEqual(checks.returncode, 0, checks.stderr)
        self.assertEqual(len(checks.stdout.splitlines()), 2573)
        parsed = list(csv.DictReader(io.StringIO(checks.stdout)))
        self.assertEqual(len(parsed), 2572)
        query = run_cli("capability-certification-query", "--domain-id", "D01", "--mvp-only")
        self.assertEqual(query.returncode, 0, query.stderr)
        self.assertEqual(len(json.loads(query.stdout)["rows"]), 4)

    def test_replay_and_failure_controls(self) -> None:
        replay = run_cli("capability-certification-replay")
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertTrue(json.loads(replay.stdout)["accepted"])
        failures = run_cli("capability-certification-failures")
        self.assertEqual(failures.returncode, 0, failures.stderr)
        self.assertTrue(json.loads(failures.stdout)["accepted"])


if __name__ == "__main__":
    unittest.main()
