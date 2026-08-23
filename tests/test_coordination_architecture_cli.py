"""CLI contract tests for the D16 coordination architecture."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "glio_noncode", *args], cwd=ROOT, text=True, capture_output=True, check=False)


class CoordinationArchitectureCliTests(unittest.TestCase):
    def test_fixture_and_data_commands(self) -> None:
        fixture = run_cli("coordination-fixture")
        self.assertEqual(0, fixture.returncode, fixture.stderr)
        self.assertEqual(64, len(json.loads(fixture.stdout)["cases"]))
        data = run_cli("coordination-data-audit")
        self.assertEqual(0, data.returncode, data.stderr)
        self.assertTrue(json.loads(data.stdout)["accepted"])

    def test_runtime_quality_depth_and_replay_commands(self) -> None:
        for command in ("coordination-runtime", "coordination-quality", "coordination-depth", "coordination-replay", "coordination-validation"):
            result = run_cli(command)
            self.assertEqual(0, result.returncode, f"{command}: {result.stderr}")
            payload = json.loads(result.stdout)
            if command == "coordination-runtime":
                self.assertEqual("accepted", payload["state"], command)
            else:
                self.assertTrue(payload["accepted"], command)

    def test_report_and_review_exports(self) -> None:
        report = run_cli("coordination-report", "--format", "markdown")
        self.assertEqual(0, report.returncode, report.stderr)
        self.assertIn("# Coordination architecture runtime", report.stdout)
        review = run_cli("coordination-review-csv")
        self.assertEqual(0, review.returncode, review.stderr)
        self.assertEqual(49, len(review.stdout.splitlines()))

    def test_static_and_control_commands(self) -> None:
        for command in ("coordination-schema", "coordination-plan", "coordination-tools", "coordination-access", "coordination-invariants", "coordination-failures"):
            result = run_cli(command)
            self.assertEqual(0, result.returncode, f"{command}: {result.stderr}")
            self.assertTrue(json.loads(result.stdout), command)

    def test_query_facets_and_checked_in_fixture(self) -> None:
        fixture = str(ROOT / "examples" / "coordination-architecture-public-aggregate.json")
        result = run_cli("coordination-query", "--input", fixture, "--state", "review")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(48, json.loads(result.stdout)["matched_count"])


if __name__ == "__main__":
    unittest.main()
