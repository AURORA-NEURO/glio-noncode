"""D10 CLI contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class LinkGraphArchitectureCliTests(unittest.TestCase):
    def test_fixture_evaluation_runtime_and_report_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, evaluation, runtime, report = (
                root / name
                for name in ("fixture.json", "evaluation.json", "runtime.json", "report.json")
            )
            self.assertEqual(main(["link-graph-architecture-fixture", "--output", str(fixture)]), 0)
            self.assertEqual(
                main(
                    [
                        "evaluate-link-graph-architecture",
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
                        "link-graph-architecture-runtime",
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
                        "link-graph-architecture-report",
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

    def test_bundle_validation_and_query_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, validation, query, bundle = (
                root / name for name in ("fixture.json", "validation.json", "query.json", "bundle")
            )
            self.assertEqual(main(["link-graph-architecture-fixture", "--output", str(fixture)]), 0)
            self.assertEqual(
                main(
                    [
                        "link-graph-architecture-validation",
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
                        "link-graph-architecture-query",
                        "--input",
                        str(fixture),
                        "--operation",
                        "D10-C13",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "link-graph-architecture-bundle",
                        "--input",
                        str(fixture),
                        "--output",
                        str(bundle),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(validation.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["count"], 4)
            self.assertTrue((bundle / "runtime.json").is_file())
            release = json.loads((bundle / "release.json").read_text(encoding="utf-8"))
            self.assertEqual(release["depth"]["check_count"], 458)
            self.assertTrue(release["quality"]["accepted"])
            self.assertTrue((bundle / "report.json").is_file())


if __name__ == "__main__":
    unittest.main()
