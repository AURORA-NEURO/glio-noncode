from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class ValidationReleaseFrontierCliTests(unittest.TestCase):
    def test_data_evaluation_and_pipeline_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.json"
            evaluation = root / "evaluation.json"
            pipeline = root / "pipeline.json"
            self.assertEqual(main(["validation-release-frontier-data-audit", "--output", str(data)]), 0)
            self.assertEqual(main(["validation-release-frontier-evaluate", "--output", str(evaluation)]), 0)
            self.assertEqual(main(["validation-release-frontier-pipeline", "--output", str(pipeline)]), 0)
            self.assertTrue(json.loads(data.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(len(json.loads(evaluation.read_text(encoding="utf-8"))["checks"]), 80)
            self.assertEqual(len(json.loads(pipeline.read_text(encoding="utf-8"))["stages"]), 50)

    def test_depth_quality_and_matrix_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ("validation-release-frontier-depth", "validation-release-frontier-thresholds", "validation-release-frontier-quality", "validation-release-frontier-validation-matrix", "validation-release-frontier-handoff", "validation-release-frontier-access", "validation-release-frontier-data-dictionary"):
                output = root / f"{command}.json"
                self.assertEqual(main([command, "--output", str(output)]), 0)
                self.assertTrue(json.loads(output.read_text(encoding="utf-8")))

    def test_report_review_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "review.csv"
            report = root / "report.md"
            failure = root / "failure.json"
            self.assertEqual(main(["validation-release-frontier-review-csv", "--output", str(review)]), 0)
            self.assertEqual(main(["validation-release-frontier-report", "--output", str(report)]), 0)
            self.assertEqual(main(["validation-release-frontier-failure-injection", "--output", str(failure)]), 0)
            self.assertEqual(len(list(csv.DictReader(review.read_text(encoding="utf-8").splitlines()))), 16)
            self.assertIn("Validation Release Frontier Report", report.read_text(encoding="utf-8"))
            self.assertTrue(json.loads(failure.read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()
