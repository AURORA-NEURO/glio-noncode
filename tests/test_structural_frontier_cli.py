from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"
PIPELINE = ROOT / "examples" / "structural-frontier-pipeline-accepted.json"


class StructuralFrontierCliTests(unittest.TestCase):
    def _run_file_command(
        self,
        command: str,
        source: Path,
        suffix: str = ".json",
        *arguments: str,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / f"output{suffix}"
            self.assertEqual(
                main([command, str(source), *arguments, "--output", str(output)]),
                0,
            )
            if suffix == ".json":
                return json.loads(output.read_text(encoding="utf-8"))
            return {"text": output.read_text(encoding="utf-8")}

    def test_fixture_and_data_boundary_commands(self) -> None:
        evaluation = self._run_file_command(
            "evaluate-structural-frontier-fixture", FIXTURE
        )
        self.assertTrue(evaluation["passed"])
        self.assertEqual(evaluation["check_count"], 72)
        self.assertEqual(len(evaluation["receipts"]), 12)

        audit = self._run_file_command("audit-structural-frontier-data", FIXTURE)
        self.assertTrue(audit["accepted"])
        self.assertEqual(audit["positive_count"], 4)
        self.assertEqual(audit["control_count"], 8)
        self.assertEqual(len(audit["source_ids"]), 4)

    def test_replay_quality_and_scenario_commands(self) -> None:
        for command in (
            "replay-structural-frontier-fixtures",
            "structural-frontier-quality-gate",
            "evaluate-structural-frontier-scenarios",
        ):
            result = self._run_file_command(command, FIXTURE)
            self.assertTrue(result["passed"], command)

        quality = self._run_file_command("structural-frontier-quality-gate", FIXTURE)
        self.assertEqual(quality["check_count"], 20)
        self.assertEqual(quality["failed_check_ids"], [])

    def test_contract_and_bundle_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(
                main(["structural-frontier-contracts", "--output", str(output)]),
                0,
            )
            contracts = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(contracts["contract_count"], 4)
        self.assertEqual(contracts["schema_version"], "structural-frontier-contracts-v1")
        self.assertEqual(
            {item["capability_id"] for item in contracts["contracts"]},
            {"GNC-D02-C13", "GNC-D02-C14", "GNC-D02-C15", "GNC-D02-C16"},
        )

        bundle = self._run_file_command(
            "build-structural-frontier-bundle",
            FIXTURE,
            ".md",
            "--format",
            "markdown",
            "--bundle-id",
            "cli-frontier-bundle",
        )
        self.assertTrue(bundle["text"].startswith("# Structural frontier evidence bundle"))
        self.assertIn("GNC-D02-C16", bundle["text"])

    def test_lineage_and_pipeline_commands(self) -> None:
        lineage = self._run_file_command("structural-frontier-lineage", FIXTURE)
        self.assertTrue(lineage["audit"]["passed"])
        self.assertEqual(lineage["node_count"], 29)
        self.assertEqual(lineage["edge_count"], 36)

        pipeline = self._run_file_command(
            "run-structural-frontier-pipeline", PIPELINE
        )
        self.assertTrue(pipeline["accepted"])
        self.assertTrue(pipeline["published"])
        self.assertEqual(pipeline["stage_count"], 4)

    def test_commands_are_registered_in_parser(self) -> None:
        parser = build_parser()
        for command in (
            "evaluate-structural-frontier-fixture",
            "audit-structural-frontier-data",
            "replay-structural-frontier-fixtures",
            "structural-frontier-quality-gate",
            "evaluate-structural-frontier-scenarios",
            "structural-frontier-contracts",
            "build-structural-frontier-bundle",
            "structural-frontier-lineage",
            "run-structural-frontier-pipeline",
        ):
            if command == "structural-frontier-contracts":
                arguments = [command]
            elif command == "build-structural-frontier-bundle":
                arguments = [command, str(FIXTURE), "--output", "bundle.json"]
            else:
                arguments = [command, str(FIXTURE)]
            parsed = parser.parse_args(arguments)
            self.assertEqual(parsed.command, command)


if __name__ == "__main__":
    unittest.main()
