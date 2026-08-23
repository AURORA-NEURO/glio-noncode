"""CLI contract tests for the C05-C08 public aggregate commands."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class CohortBetaFrontierCliTests(unittest.TestCase):
    def test_fixture_command_emits_sixteen_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fixture.json"
            self.assertEqual(main(["cohort-beta-frontier-fixture", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["records"]), 16)

    def test_quality_replay_and_report_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            quality = Path(directory) / "quality.json"
            replay = Path(directory) / "replay.json"
            report = Path(directory) / "report.md"
            self.assertEqual(main(["cohort-beta-frontier-quality", "--output", str(quality)]), 0)
            self.assertEqual(main(["cohort-beta-frontier-replay", "--output", str(replay)]), 0)
            self.assertEqual(main(["cohort-beta-frontier-report", "--format", "markdown", "--output", str(report)]), 0)
            self.assertTrue(json.loads(quality.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(replay.read_text(encoding="utf-8"))["deterministic"])
            self.assertIn("Domain 12 C05-C08", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
