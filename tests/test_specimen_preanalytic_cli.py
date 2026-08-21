from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-preanalytic-public-aggregate.json"
PIPELINE = ROOT / "examples" / "specimen-preanalytic-pipeline-accepted.json"
REVIEW_PIPELINE = ROOT / "examples" / "specimen-preanalytic-pipeline-review.json"


class SpecimenPreanalyticCliTests(unittest.TestCase):
    def _run_json(self, command: str, source: Path, *extra: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / f"{command}.json"
            code = main([command, str(source), *extra, "--output", str(output)])
            self.assertEqual(code, 0, command)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_all_commands_are_parser_registered(self) -> None:
        parser = build_parser()
        commands = {
            "evaluate-specimen-preanalytic-fixture",
            "audit-specimen-preanalytic-data",
            "replay-specimen-preanalytic-fixtures",
            "specimen-preanalytic-quality-gate",
            "evaluate-specimen-preanalytic-scenarios",
            "specimen-preanalytic-contracts",
            "build-specimen-preanalytic-bundle",
            "specimen-preanalytic-lineage",
            "specimen-preanalytic-reconciliation",
            "run-specimen-preanalytic-pipeline",
        }
        choices = set(parser._subparsers._group_actions[0].choices)
        self.assertTrue(commands.issubset(choices))

    def test_fixture_data_replay_quality_and_scenario_commands(self) -> None:
        for command in (
            "evaluate-specimen-preanalytic-fixture",
            "audit-specimen-preanalytic-data",
            "replay-specimen-preanalytic-fixtures",
            "specimen-preanalytic-quality-gate",
            "evaluate-specimen-preanalytic-scenarios",
        ):
            result = self._run_json(command, FIXTURE)
            self.assertTrue(result.get("passed", result.get("accepted", False)), command)

    def test_contract_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(main(["specimen-preanalytic-contracts", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["contract_count"], 4)

    def test_bundle_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for suffix, format_name in (("json", "json"), ("csv", "csv"), ("md", "markdown")):
                output = Path(directory) / f"bundle.{suffix}"
                code = main(
                    [
                        "build-specimen-preanalytic-bundle",
                        str(FIXTURE),
                        "--output",
                        str(output),
                        "--format",
                        format_name,
                    ]
                )
                self.assertEqual(code, 0)
                self.assertTrue(output.read_text(encoding="utf-8"))

    def test_lineage_reconciliation_and_pipeline_commands(self) -> None:
        graph = self._run_json("specimen-preanalytic-lineage", FIXTURE)
        self.assertTrue(graph["audit"]["passed"])
        self.assertEqual(graph["node_count"], 29)
        reconciliation = self._run_json("specimen-preanalytic-reconciliation", FIXTURE)
        self.assertTrue(reconciliation["audit"]["passed"])
        self.assertEqual(reconciliation["entry_count"], 12)
        pipeline = self._run_json("run-specimen-preanalytic-pipeline", PIPELINE)
        self.assertTrue(pipeline["published"])
        self.assertEqual(pipeline["stage_count"], 4)

    def test_review_pipeline_returns_nonzero_without_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review.json"
            code = main(
                ["run-specimen-preanalytic-pipeline", str(REVIEW_PIPELINE), "--output", str(output)]
            )
            self.assertEqual(code, 2)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "review")
            self.assertFalse(payload["published"])


if __name__ == "__main__":
    unittest.main()
