from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class WorkspaceBetaFrontierCliTests(unittest.TestCase):
    def _run(self, root: Path, command: str) -> dict[str, object]:
        output = root / f"{command}.json"
        self.assertEqual(main([command, "--output", str(output)]), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_evaluation_runtime_and_release_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluation = self._run(root, "beta-frontier-evaluate")
            self.assertTrue(evaluation["accepted"])
            self.assertEqual(len(evaluation["executions"]), 16)
            runtime = self._run(root, "beta-frontier-runtime")
            self.assertTrue(runtime["accepted"])
            self.assertEqual(len(runtime["stages"]), 8)
            release = self._run(root, "beta-frontier-release")
            self.assertEqual(release["state"], "ready")

    def test_quality_review_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quality = self._run(root, "beta-frontier-quality-gate")
            self.assertTrue(quality["accepted"])
            queue = self._run(root, "beta-frontier-review-queue")
            self.assertEqual(len(queue["items"]), 13)
            csv_path = root / "review.csv"
            self.assertEqual(main(["export-beta-frontier-review-csv", "--output", str(csv_path)]), 0)
            text = csv_path.read_text(encoding="utf-8")
            self.assertIn("record_id", text)
            self.assertIn("topology-foreign-context", text)

    def test_shape_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ("beta-frontier-contracts", "beta-frontier-schema", "beta-frontier-adapters", "beta-frontier-scenarios", "beta-frontier-thresholds", "beta-frontier-invariants"):
                payload = self._run(root, command)
                self.assertTrue(payload)


if __name__ == "__main__":
    unittest.main()
