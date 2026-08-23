from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class DeploymentFrontierCliTests(unittest.TestCase):
    def test_data_and_evaluation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.json"
            evaluation = root / "evaluation.json"
            self.assertEqual(main(["deployment-frontier-data-audit", "--output", str(data)]), 0)
            self.assertEqual(main(["deployment-frontier-evaluate", "--output", str(evaluation)]), 0)
            self.assertTrue(json.loads(data.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(len(json.loads(evaluation.read_text(encoding="utf-8"))["checks"]), 80)

    def test_pipeline_and_depth_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = root / "pipeline.json"
            depth = root / "depth.json"
            self.assertEqual(main(["deployment-frontier-pipeline", "--output", str(pipeline)]), 0)
            self.assertEqual(main(["deployment-frontier-depth", "--output", str(depth)]), 0)
            self.assertTrue(json.loads(pipeline.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(depth.read_text(encoding="utf-8"))["accepted"])

    def test_review_csv_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "review.csv"
            report = root / "report.md"
            self.assertEqual(main(["deployment-frontier-review-csv", "--output", str(review)]), 0)
            self.assertEqual(main(["deployment-frontier-report", "--output", str(report)]), 0)
            rows = list(csv.DictReader(review.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(len(rows), 16)
            self.assertIn("Deployment Frontier Report", report.read_text(encoding="utf-8"))

    def test_failure_injection_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failure.json"
            self.assertEqual(main(["deployment-frontier-failure-injection", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(len(payload["probes"]), 12)


if __name__ == "__main__":
    unittest.main()
