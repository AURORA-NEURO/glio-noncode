"""D16 CLI contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class PlatformExecutionArchitectureCliTests(unittest.TestCase):
    def test_fixture_evaluation_runtime_and_report_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, evaluation, runtime, report = (
                root / name
                for name in ("fixture.json", "evaluation.json", "runtime.json", "report.json")
            )
            self.assertEqual(
                main(["platform-execution-architecture-fixture", "--output", str(fixture)]),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "evaluate-platform-execution-architecture",
                        "--input",
                        str(fixture),
                        "--output",
                        str(evaluation),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "platform-execution-architecture-runtime",
                        "--input",
                        str(fixture),
                        "--output",
                        str(runtime),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "platform-execution-architecture-report",
                        "--input",
                        str(fixture),
                        "--output",
                        str(report),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(evaluation.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(runtime.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(
                json.loads(report.read_text(encoding="utf-8"))["metrics"]["case_count"], 64
            )

    def test_validation_query_and_bundle_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, validation, query, bundle = (
                root / name for name in ("fixture.json", "validation.json", "query.json", "bundle")
            )
            self.assertEqual(
                main(["platform-execution-architecture-fixture", "--output", str(fixture)]),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "platform-execution-architecture-validation",
                        "--input",
                        str(fixture),
                        "--output",
                        str(validation),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "platform-execution-architecture-query",
                        "--input",
                        str(fixture),
                        "--operation",
                        "D16-C14",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "platform-execution-architecture-bundle",
                        "--input",
                        str(fixture),
                        "--output",
                        str(bundle),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(validation.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(len(json.loads(query.read_text(encoding="utf-8"))["rows"]), 4)
            self.assertTrue((bundle / "runtime.json").is_file())
            self.assertTrue((bundle / "report.json").is_file())


if __name__ == "__main__":
    unittest.main()
