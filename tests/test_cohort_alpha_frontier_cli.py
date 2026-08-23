"""CLI contract tests for the C09-C12 public aggregate commands."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class CohortAlphaFrontierCliTests(unittest.TestCase):
    def test_fixture_command_emits_sixteen_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fixture.json"
            self.assertEqual(main(["cohort-alpha-frontier-fixture", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["records"]), 16)
            self.assertEqual(payload["fixture_version"], "2026.08.d12-c09-c12.v1")

    def test_evaluate_quality_replay_and_report_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evaluation = Path(directory) / "evaluation.json"
            quality = Path(directory) / "quality.json"
            replay = Path(directory) / "replay.json"
            report = Path(directory) / "report.md"
            self.assertEqual(main(["cohort-alpha-frontier-evaluate", "--output", str(evaluation)]), 0)
            self.assertEqual(main(["cohort-alpha-frontier-quality", "--output", str(quality)]), 0)
            self.assertEqual(main(["cohort-alpha-frontier-replay", "--output", str(replay)]), 0)
            self.assertEqual(main(["cohort-alpha-frontier-report", "--format", "markdown", "--output", str(report)]), 0)
            self.assertEqual(len(json.loads(evaluation.read_text(encoding="utf-8"))["rows"]), 16)
            self.assertTrue(json.loads(quality.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(replay.read_text(encoding="utf-8"))["deterministic"])
            self.assertIn("cohort alpha frontier", report.read_text(encoding="utf-8").lower())

    def test_complete_pipeline_emits_accepted_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runtime.json"
            self.assertEqual(main(["run-cohort-alpha-frontier-pipeline", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertGreaterEqual(len(payload["stages"]), 70)
            self.assertEqual(payload["policy"]["publishable_count"], 4)


if __name__ == "__main__":
    unittest.main()
