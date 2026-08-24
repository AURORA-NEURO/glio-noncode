"""CLI contract tests for D09."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class TopologyArchitectureCliTests(unittest.TestCase):
    def test_fixture_evaluation_runtime_and_report_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.json"
            evaluation = root / "evaluation.json"
            runtime = root / "runtime.json"
            report = root / "report.json"
            self.assertEqual(main(["topology-architecture-fixture", "--output", str(fixture)]), 0)
            self.assertEqual(
                main(
                    [
                        "evaluate-topology-architecture",
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
                        "topology-architecture-runtime",
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
                        "topology-architecture-report",
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
            self.assertEqual(
                json.loads(report.read_text(encoding="utf-8"))["depth"]["check_count"], 458
            )

    def test_bundle_validation_and_query_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.json"
            bundle = root / "bundle"
            validation = root / "validation.json"
            query = root / "query.json"
            self.assertEqual(main(["topology-architecture-fixture", "--output", str(fixture)]), 0)
            self.assertEqual(
                main(
                    [
                        "topology-architecture-validation",
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
                        "topology-architecture-query",
                        "--input",
                        str(fixture),
                        "--operation",
                        "D09-C13",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "topology-architecture-bundle",
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
            self.assertTrue((bundle / "report.json").is_file())
            release = json.loads((bundle / "release.json").read_text(encoding="utf-8"))
            self.assertEqual(release["depth"]["check_count"], 458)
            self.assertTrue(release["quality"]["accepted"])


if __name__ == "__main__":
    unittest.main()
