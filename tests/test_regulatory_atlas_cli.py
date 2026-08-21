from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class RegulatoryAtlasCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example = Path("examples/regulatory-atlas-public-aggregate.json")
        self.pipeline_example = Path("examples/regulatory-atlas-pipeline-accepted.json")

    def _run(self, arguments: list[str], directory: Path) -> dict:
        output = directory / "output.json"
        result = main(arguments + ["--output", str(output)])
        self.assertEqual(result, 0, arguments)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_fixture_data_replay_quality_and_scenarios_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            for command in (
                "evaluate-regulatory-atlas-fixture",
                "audit-regulatory-atlas-data",
                "replay-regulatory-atlas-fixtures",
                "regulatory-atlas-quality-gate",
                "evaluate-regulatory-atlas-scenarios",
            ):
                payload = self._run([command, str(self.example)], directory)
                self.assertTrue(payload["accepted"], command)

    def test_contracts_and_metrics_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            contracts = self._run(["regulatory-atlas-contracts"], directory)
            self.assertEqual(len(contracts["contracts"]), 4)
            metrics = self._run(["regulatory-atlas-metrics", str(self.example)], directory)
            self.assertTrue(metrics["accepted"])
            self.assertEqual(metrics["totals"]["receipts"], 16)
            self.assertEqual(metrics["totals"]["checks"], 120)
            self.assertNotIn("input_text", json.dumps(metrics))

    def test_bundle_command_writes_each_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            for output_format, suffix in (("json", ".json"), ("csv", ".csv"), ("markdown", ".md")):
                output = directory / f"bundle{suffix}"
                result = main(
                    [
                        "build-regulatory-atlas-bundle",
                        str(self.example),
                        "--output",
                        str(output),
                        "--format",
                        output_format,
                        "--accepted-only",
                    ]
                )
                self.assertEqual(result, 0, output_format)
                text = output.read_text(encoding="utf-8")
                self.assertTrue(text)
                if output_format == "json":
                    self.assertEqual(len(json.loads(text)["entries"]), 4)
                if output_format == "csv":
                    self.assertIn("record_id,operation,role,state", text)
                if output_format == "markdown":
                    self.assertIn("# Regulatory atlas bundle", text)

    def test_lineage_and_reconciliation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            lineage = self._run(["regulatory-atlas-lineage", str(self.example)], directory)
            self.assertTrue(lineage["accepted"])
            self.assertEqual(lineage["audit"]["node_count"], 157)
            self.assertEqual(lineage["audit"]["edge_count"], 157)
            reconciliation = self._run(
                ["regulatory-atlas-reconciliation", str(self.example)], directory
            )
            self.assertTrue(reconciliation["accepted"])

    def test_pipeline_and_release_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            pipeline_output = directory / "pipeline.json"
            result = main(
                [
                    "run-regulatory-atlas-pipeline",
                    str(self.pipeline_example),
                    "--output",
                    str(pipeline_output),
                ]
            )
            self.assertEqual(result, 0)
            pipeline = json.loads(pipeline_output.read_text(encoding="utf-8"))
            self.assertTrue(pipeline["published"])
            self.assertEqual(len(pipeline["stages"]), 9)
            release_output = directory / "release.json"
            result = main(
                [
                    "build-regulatory-atlas-release",
                    str(self.example),
                    "--output",
                    str(release_output),
                ]
            )
            self.assertEqual(result, 0)
            release = json.loads(release_output.read_text(encoding="utf-8"))
            self.assertTrue(release["publishable"])
            self.assertEqual(release["state"], "published")


if __name__ == "__main__":
    unittest.main()
