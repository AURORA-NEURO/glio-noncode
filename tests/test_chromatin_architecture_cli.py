"""CLI contract tests for D07."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class ChromatinArchitectureCliTests(unittest.TestCase):
    def test_fixture_audit_plan_and_evaluation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.json"
            audit = root / "audit.json"
            plan = root / "plan.json"
            evaluation = root / "evaluation.json"
            self.assertEqual(main(["chromatin-architecture-fixture", "--output", str(fixture)]), 0)
            self.assertEqual(
                main(
                    [
                        "chromatin-architecture-data-audit",
                        "--input",
                        str(fixture),
                        "--output",
                        str(audit),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    ["chromatin-architecture-plan", "--input", str(fixture), "--output", str(plan)]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "evaluate-chromatin-architecture",
                        "--input",
                        str(fixture),
                        "--output",
                        str(evaluation),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(evaluation.read_text(encoding="utf-8"))["accepted"])

    def test_runtime_quality_validation_and_reporting_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.json"
            quality = root / "quality.json"
            validation = root / "validation.json"
            report = root / "report.md"
            self.assertEqual(main(["chromatin-architecture-runtime", "--output", str(runtime)]), 0)
            self.assertEqual(main(["chromatin-architecture-quality", "--output", str(quality)]), 0)
            self.assertEqual(
                main(["chromatin-architecture-validation", "--output", str(validation)]), 0
            )
            self.assertEqual(
                main(
                    [
                        "chromatin-architecture-report",
                        "--format",
                        "markdown",
                        "--output",
                        str(report),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(runtime.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(validation.read_text(encoding="utf-8"))["accepted"])
            self.assertIn("D07 Chromatin Architecture Report", report.read_text(encoding="utf-8"))

    def test_bundle_csv_scenarios_sources_and_compliance_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            receipts = root / "receipts.csv"
            review = root / "review.csv"
            scenarios = root / "scenarios.json"
            sources = root / "sources.json"
            compliance = root / "compliance.json"
            self.assertEqual(main(["chromatin-architecture-bundle", "--output", str(bundle)]), 0)
            self.assertEqual(
                main(["chromatin-architecture-receipts-csv", "--output", str(receipts)]), 0
            )
            self.assertEqual(
                main(["chromatin-architecture-review-csv", "--output", str(review)]), 0
            )
            self.assertEqual(
                main(["chromatin-architecture-scenarios", "--output", str(scenarios)]), 0
            )
            self.assertEqual(main(["chromatin-architecture-sources", "--output", str(sources)]), 0)
            self.assertEqual(
                main(["chromatin-architecture-compliance", "--output", str(compliance)]), 0
            )
            self.assertTrue((bundle / "runtime.json").is_file())
            self.assertEqual(len(receipts.read_text(encoding="utf-8").splitlines()), 65)
            self.assertEqual(len(review.read_text(encoding="utf-8").splitlines()), 49)
            self.assertTrue(json.loads(scenarios.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(sources.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(compliance.read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()
