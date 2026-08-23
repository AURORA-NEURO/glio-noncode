"""CLI coverage for the D04 public reference architecture surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReferenceArchitectureCliTests(unittest.TestCase):
    def run_cli(
        self, *arguments: str, output: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, "-m", "glio_noncode", *arguments]
        if output is not None:
            command.extend(("--output", str(output)))
        return subprocess.run(command, check=False, capture_output=True, text=True)

    def test_fixture_audit_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.run_cli("reference-architecture-fixture", output=root / "fixture.json")
            audit = self.run_cli(
                "reference-architecture-data-audit",
                "--input",
                str(root / "fixture.json"),
                output=root / "audit.json",
            )
            plan = self.run_cli(
                "reference-architecture-plan",
                "--input",
                str(root / "fixture.json"),
                output=root / "plan.json",
            )
            self.assertEqual(fixture.returncode, 0, fixture.stderr)
            self.assertEqual(audit.returncode, 0, audit.stderr)
            self.assertEqual(plan.returncode, 0, plan.stderr)
            self.assertTrue(json.loads((root / "audit.json").read_text())["accepted"])
            self.assertTrue(json.loads((root / "plan.json").read_text())["accepted"])

    def test_evaluation_runtime_quality_depth_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in (
                "evaluate-reference-architecture",
                "reference-architecture-runtime",
                "reference-architecture-quality",
                "reference-architecture-depth",
                "replay-reference-architecture",
                "reference-architecture-validation",
            ):
                result = self.run_cli(command, output=root / f"{command}.json")
                self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            self.assertTrue(
                json.loads((root / "evaluate-reference-architecture.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "reference-architecture-runtime.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "reference-architecture-quality.json").read_text())["passed"]
            )
            self.assertTrue(
                json.loads((root / "reference-architecture-depth.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "replay-reference-architecture.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "reference-architecture-validation.json").read_text())[
                    "accepted"
                ]
            )

    def test_review_query_and_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = self.run_cli("reference-architecture-review", output=root / "review.json")
            query = self.run_cli(
                "reference-architecture-query", "--state", "review", output=root / "query.json"
            )
            bundle = self.run_cli("reference-architecture-bundle", "--output", str(root / "bundle"))
            self.assertEqual(review.returncode, 0, review.stderr)
            self.assertEqual(query.returncode, 0, query.stderr)
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            self.assertEqual(len(json.loads((root / "review.json").read_text())["items"]), 48)
            self.assertEqual(len(json.loads((root / "query.json").read_text())["receipts"]), 48)
            self.assertTrue((root / "bundle" / "runtime.json").exists())
            self.assertTrue((root / "bundle" / "release.json").exists())


if __name__ == "__main__":
    unittest.main()
