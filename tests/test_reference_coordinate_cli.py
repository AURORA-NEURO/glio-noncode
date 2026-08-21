from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "reference-coordinate-public-aggregate.json"
PIPELINE = ROOT / "examples" / "reference-coordinate-pipeline-accepted.json"
REVIEW_PIPELINE = ROOT / "examples" / "reference-coordinate-pipeline-review.json"


class ReferenceCoordinateCliTests(unittest.TestCase):
    def _run_json(self, command: str, source: Path, *extra: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / f"{command}.json"
            code = main([command, str(source), *extra, "--output", str(output)])
            self.assertEqual(code, 0, command)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_all_c01_c04_commands_are_parser_registered(self) -> None:
        parser = build_parser()
        expected = {
            "evaluate-reference-coordinate-fixture",
            "audit-reference-coordinate-data",
            "replay-reference-coordinate-fixtures",
            "reference-coordinate-quality-gate",
            "evaluate-reference-coordinate-scenarios",
            "reference-coordinate-contracts",
            "build-reference-coordinate-bundle",
            "reference-coordinate-lineage",
            "reference-coordinate-reconciliation",
            "run-reference-coordinate-pipeline",
        }
        choices = set(parser._subparsers._group_actions[0].choices)
        self.assertTrue(expected.issubset(choices))

    def test_data_evaluation_replay_quality_and_scenarios_commands(self) -> None:
        for command in (
            "audit-reference-coordinate-data",
            "evaluate-reference-coordinate-fixture",
            "replay-reference-coordinate-fixtures",
            "reference-coordinate-quality-gate",
            "evaluate-reference-coordinate-scenarios",
        ):
            result = self._run_json(command, FIXTURE)
            self.assertTrue(result.get("passed", result.get("state") == "accepted"), command)

    def test_contract_command_emits_four_operation_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(main(["reference-coordinate-contracts", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["operation_count"], 4)
            self.assertEqual(
                payload["capability_ids"],
                [
                    "GNC-D04-C01",
                    "GNC-D04-C02",
                    "GNC-D04-C03",
                    "GNC-D04-C04",
                ],
            )

    def test_bundle_formats_and_accepted_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for suffix, format_name, marker in (
                ("json", "json", '"entries"'),
                ("csv", "csv", "record_id,operation"),
                ("md", "markdown", "| Record | Operation |"),
            ):
                output = Path(directory) / f"bundle.{suffix}"
                code = main(
                    [
                        "build-reference-coordinate-bundle",
                        str(FIXTURE),
                        "--output",
                        str(output),
                        "--format",
                        format_name,
                    ]
                )
                self.assertEqual(code, 0)
                self.assertIn(marker, output.read_text(encoding="utf-8"))
            accepted = Path(directory) / "accepted.json"
            self.assertEqual(
                main(
                    [
                        "build-reference-coordinate-bundle",
                        str(FIXTURE),
                        "--output",
                        str(accepted),
                        "--accepted-only",
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(accepted.read_text(encoding="utf-8"))["entry_count"], 4)

    def test_lineage_reconciliation_and_pipeline_commands(self) -> None:
        graph = self._run_json("reference-coordinate-lineage", FIXTURE)
        self.assertTrue(graph["audit"]["passed"])
        self.assertEqual(graph["node_count"], 39)
        self.assertEqual(graph["edge_count"], 38)
        reconciliation = self._run_json("reference-coordinate-reconciliation", FIXTURE)
        self.assertTrue(reconciliation["passed"])
        self.assertEqual(reconciliation["check_count"], 24)
        pipeline = self._run_json("run-reference-coordinate-pipeline", PIPELINE)
        self.assertTrue(pipeline["published"])
        self.assertEqual(pipeline["stage_count"], 5)

    def test_review_pipeline_returns_nonzero_without_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review.json"
            code = main(
                ["run-reference-coordinate-pipeline", str(REVIEW_PIPELINE), "--output", str(output)]
            )
            self.assertEqual(code, 2)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "review")
            self.assertFalse(payload["published"])


if __name__ == "__main__":
    unittest.main()
