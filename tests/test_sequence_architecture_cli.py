"""CLI coverage for the D06 public sequence architecture surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SequenceArchitectureCliTests(unittest.TestCase):
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
            fixture = self.run_cli("sequence-architecture-fixture", output=root / "fixture.json")
            audit = self.run_cli(
                "sequence-architecture-data-audit",
                "--input",
                str(root / "fixture.json"),
                output=root / "audit.json",
            )
            plan = self.run_cli(
                "sequence-architecture-plan",
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
                "evaluate-sequence-architecture",
                "sequence-architecture-runtime",
                "sequence-architecture-quality",
                "sequence-architecture-depth",
                "replay-sequence-architecture",
                "sequence-architecture-validation",
            ):
                result = self.run_cli(command, output=root / f"{command}.json")
                self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            self.assertTrue(
                json.loads((root / "evaluate-sequence-architecture.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "sequence-architecture-runtime.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "sequence-architecture-quality.json").read_text())["passed"]
            )
            self.assertTrue(
                json.loads((root / "sequence-architecture-depth.json").read_text())["accepted"]
            )
            self.assertEqual(
                json.loads((root / "sequence-architecture-depth.json").read_text())[
                    "completion_percent"
                ],
                100.0,
            )
            self.assertTrue(
                json.loads((root / "replay-sequence-architecture.json").read_text())["accepted"]
            )
            self.assertTrue(
                json.loads((root / "sequence-architecture-validation.json").read_text())["accepted"]
            )

    def test_scenarios_query_bundle_and_runbook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenarios = self.run_cli(
                "sequence-architecture-scenarios", output=root / "scenarios.json"
            )
            query = self.run_cli(
                "sequence-architecture-query",
                "--state",
                "review",
                output=root / "query.json",
            )
            runbook = self.run_cli("sequence-architecture-runbook", output=root / "runbook.json")
            bundle = self.run_cli("sequence-architecture-bundle", "--output", str(root / "bundle"))
            self.assertEqual(scenarios.returncode, 0, scenarios.stderr)
            self.assertEqual(query.returncode, 0, query.stderr)
            self.assertEqual(runbook.returncode, 0, runbook.stderr)
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            self.assertEqual(
                json.loads((root / "scenarios.json").read_text())["summary"]["scenario_counts"][
                    "positive"
                ],
                16,
            )
            self.assertEqual(len(json.loads((root / "query.json").read_text())["receipts"]), 48)
            self.assertTrue(json.loads((root / "runbook.json").read_text())["accepted"])
            self.assertTrue((root / "bundle" / "runtime.json").exists())
            self.assertTrue((root / "bundle" / "release.json").exists())
            self.assertTrue((root / "bundle" / "report.json").exists())
            bundle_release = json.loads((root / "bundle" / "release.json").read_text())
            self.assertEqual(len(bundle_release["quality"]["checks"]), 12)


if __name__ == "__main__":
    unittest.main()
