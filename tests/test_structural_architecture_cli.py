"""CLI coverage for the D02 structural architecture surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class StructuralArchitectureCliTests(unittest.TestCase):
    def run_cli(
        self, *arguments: str, output: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, "-m", "glio_noncode", *arguments]
        if output is not None:
            command.extend(("--output", str(output)))
        return subprocess.run(command, check=False, capture_output=True, text=True)

    def test_fixture_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "fixture.json"
            audit_path = Path(directory) / "audit.json"
            fixture = self.run_cli("structural-architecture-fixture", output=fixture_path)
            audit = self.run_cli(
                "structural-architecture-data-audit",
                "--input",
                str(fixture_path),
                output=audit_path,
            )
            self.assertEqual(fixture.returncode, 0, fixture.stderr)
            self.assertEqual(audit.returncode, 0, audit.stderr)
            self.assertTrue(json.loads(audit_path.read_text())["accepted"])

    def test_plan_evaluation_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in (
                "structural-architecture-plan",
                "evaluate-structural-architecture",
                "structural-architecture-validation",
            ):
                result = self.run_cli(command, output=root / f"{command}.json")
                self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            self.assertTrue(
                json.loads((root / "evaluate-structural-architecture.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "structural-architecture-validation.json").read_text())[
                    "accepted"
                ]
            )

    def test_runtime_quality_and_depth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in (
                "structural-architecture-runtime",
                "structural-architecture-quality",
                "structural-architecture-depth",
            ):
                result = self.run_cli(command, output=root / f"{command}.json")
                self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            self.assertTrue(
                json.loads((root / "structural-architecture-runtime.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "structural-architecture-quality.json").read_text())["passed"]
            )
            self.assertTrue(
                json.loads((root / "structural-architecture-depth.json").read_text())["accepted"]
            )

    def test_review_report_and_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = self.run_cli("structural-architecture-review-csv", output=root / "review.csv")
            report = self.run_cli(
                "structural-architecture-report", "--format", "markdown", output=root / "report.md"
            )
            bundle = self.run_cli(
                "structural-architecture-bundle", "--output", str(root / "bundle")
            )
            self.assertEqual(review.returncode, 0, review.stderr)
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            self.assertIn("case_id,operation_id", (root / "review.csv").read_text())
            self.assertIn("# Structural architecture release", (root / "report.md").read_text())
            self.assertTrue((root / "bundle" / "release.json").exists())

    def test_replay_schema_failures_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = (
                "replay-structural-architecture",
                "structural-architecture-schema",
                "structural-architecture-failures",
                "structural-architecture-metrics",
                "structural-architecture-invariants",
                "structural-architecture-access",
            )
            for command in commands:
                result = self.run_cli(command, output=root / f"{command}.json")
                self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            self.assertTrue(
                json.loads((root / "replay-structural-architecture.json").read_text())[
                    "deterministic"
                ]
            )
            self.assertTrue(
                json.loads((root / "structural-architecture-failures.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "structural-architecture-invariants.json").read_text())[
                    "accepted"
                ]
            )

    def test_query_filters_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "query.json"
            result = self.run_cli(
                "structural-architecture-query",
                "--state",
                "review",
                "--issue-code",
                "context_mismatch",
                output=result_path,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result_path.read_text())
            self.assertEqual(len(payload["matched_case_ids"]), 16)
            self.assertEqual(payload["issue_codes"], ["context_mismatch"])


if __name__ == "__main__":
    unittest.main()
