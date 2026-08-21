"""CLI surface tests for Domain 03 C01-C04."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-frontier-public-aggregate.json"
PIPELINE = ROOT / "examples" / "specimen-frontier-pipeline-accepted.json"


class SpecimenFrontierCliTests(unittest.TestCase):
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

    def test_fixture_and_data_commands(self) -> None:
        evaluation = self._run_file_command("evaluate-specimen-frontier-fixture", FIXTURE)
        self.assertTrue(evaluation["passed"])
        self.assertEqual(evaluation["check_count"], 72)
        self.assertEqual(len(evaluation["receipts"]), 12)

        audit = self._run_file_command("audit-specimen-frontier-data", FIXTURE)
        self.assertTrue(audit["accepted"])
        self.assertEqual(audit["positive_count"], 4)
        self.assertEqual(audit["control_count"], 8)

    def test_replay_quality_and_scenario_commands(self) -> None:
        for command in (
            "replay-specimen-frontier-fixtures",
            "specimen-frontier-quality-gate",
            "evaluate-specimen-frontier-scenarios",
        ):
            result = self._run_file_command(command, FIXTURE)
            self.assertTrue(result["passed"], command)
        quality = self._run_file_command("specimen-frontier-quality-gate", FIXTURE)
        self.assertEqual(quality["check_count"], 21)
        self.assertEqual(quality["failed_check_ids"], [])

    def test_contract_bundle_and_lineage_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(
                main(["specimen-frontier-contracts", "--output", str(output)]),
                0,
            )
            contracts = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(contracts["contract_count"], 4)
        self.assertEqual(contracts["schema_version"], "specimen-frontier-contracts-v1")

        bundle = self._run_file_command(
            "build-specimen-frontier-bundle",
            FIXTURE,
            ".md",
            "--format",
            "markdown",
            "--bundle-id",
            "cli-specimen-frontier-bundle",
        )
        self.assertTrue(bundle["text"].startswith("# Specimen frontier evidence bundle"))
        self.assertIn("GNC-D03-C04", bundle["text"])

        lineage = self._run_file_command("specimen-frontier-lineage", FIXTURE)
        self.assertTrue(lineage["audit"]["passed"])
        self.assertEqual(lineage["node_count"], 29)
        self.assertEqual(lineage["edge_count"], 36)

    def test_pipeline_command_publishes_manifest(self) -> None:
        result = self._run_file_command("run-specimen-frontier-pipeline", PIPELINE)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["published"])
        self.assertEqual(result["stage_count"], 4)

    def test_commands_are_registered_in_parser(self) -> None:
        parser = build_parser()
        for command in (
            "evaluate-specimen-frontier-fixture",
            "audit-specimen-frontier-data",
            "replay-specimen-frontier-fixtures",
            "specimen-frontier-quality-gate",
            "evaluate-specimen-frontier-scenarios",
            "specimen-frontier-contracts",
            "build-specimen-frontier-bundle",
            "specimen-frontier-lineage",
            "run-specimen-frontier-pipeline",
        ):
            if command == "specimen-frontier-contracts":
                arguments = [command]
            elif command == "build-specimen-frontier-bundle":
                arguments = [command, str(FIXTURE), "--output", "bundle.json"]
            else:
                arguments = [command, str(FIXTURE)]
            parsed = parser.parse_args(arguments)
            self.assertEqual(parsed.command, command)


if __name__ == "__main__":
    unittest.main()
