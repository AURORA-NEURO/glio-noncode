from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import build_parser, main

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"
ROOT = Path(__file__).resolve().parents[1]
BETA_FIXTURE = ROOT / "examples" / "structural-beta-public-aggregate.json"
BETA_PIPELINE = ROOT / "examples" / "structural-beta-pipeline-accepted.json"


class StructuralBetaCliTests(unittest.TestCase):
    def _run(self, command: str, payload: object, *arguments: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            output = root / "output.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                main([command, str(source), *arguments, "--output", str(output)]),
                0,
            )
            return json.loads(output.read_text(encoding="utf-8"))

    def test_map_focal_amplification_command(self) -> None:
        payload = {
            "records": [
                {
                    "segment_id": "s1",
                    "caller_id": "caller-a",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "copy_number": 8,
                    "context_key": CONTEXT,
                },
                {
                    "segment_id": "s2",
                    "caller_id": "caller-b",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "copy_number": 7,
                    "context_key": CONTEXT,
                },
            ]
        }
        result = self._run("map-focal-amplification", payload, "--context-key", CONTEXT)
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["start"], 100)

    def test_detect_chromothripsis_command(self) -> None:
        payload = {
            "records": [
                {
                    "event_id": f"sv-{index}",
                    "chrom": "7",
                    "pos": 1000 + index * 100,
                    "orientation": "forward" if index % 2 == 0 else "reverse",
                    "copy_number_state": "high" if index % 2 == 0 else "low",
                }
                for index in range(6)
            ]
        }
        result = self._run(
            "detect-chromothripsis",
            payload,
            "--min-orientation-switches",
            "3",
        )
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["breakpoint_count"], 6)

    def test_detect_ecdna_command(self) -> None:
        payload = {
            "records": [
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-a",
                    "is_circular": True,
                    "junction_count": 3,
                    "copy_number": 12,
                },
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-b",
                    "is_circular": True,
                    "junction_count": 3,
                    "copy_number": 11,
                },
            ]
        }
        result = self._run("detect-ecdna", payload)
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["component_id"], "cycle-1")

    def test_detect_enhancer_hijacking_command(self) -> None:
        payload = {
            "records": [
                {
                    "event_id": "sv-1",
                    "enhancer_id": "enh-1",
                    "target_gene_id": "gene-a",
                    "context_key": CONTEXT,
                    "breakpoint_supported": True,
                    "activity_supported": True,
                }
            ]
        }
        result = self._run(
            "detect-enhancer-hijacking",
            payload,
            "--context-key",
            CONTEXT,
            "--minimum-evidence-channels",
            "2",
        )
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["target_gene_id"], "gene-a")

    def _run_file_command(self, command: str, source: Path, suffix: str = ".json", *arguments: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / f"output{suffix}"
            self.assertEqual(
                main([command, str(source), *arguments, "--output", str(output)]),
                0,
            )
            if suffix == ".json":
                return json.loads(output.read_text(encoding="utf-8"))
            return {"text": output.read_text(encoding="utf-8")}

    def test_beta_fixture_evaluation_command(self) -> None:
        result = self._run_file_command("evaluate-structural-beta-fixture", BETA_FIXTURE)
        self.assertTrue(result["passed"])
        self.assertEqual(result["check_count"], 63)
        self.assertEqual(len(result["receipts"]), 12)

    def test_beta_data_audit_command(self) -> None:
        result = self._run_file_command("audit-structural-beta-data", BETA_FIXTURE)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["positive_count"], 4)
        self.assertEqual(result["control_count"], 8)

    def test_beta_replay_quality_and_scenario_commands(self) -> None:
        for command in (
            "replay-structural-beta-fixtures",
            "structural-beta-quality-gate",
            "evaluate-structural-beta-scenarios",
        ):
            result = self._run_file_command(command, BETA_FIXTURE)
            self.assertTrue(result["passed"], command)

    def test_beta_contract_manifest_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(main(["structural-beta-contracts", "--output", str(output)]), 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["contract_count"], 4)
            self.assertEqual(result["schema_version"], "structural-beta-contracts-v1")

    def test_beta_bundle_command_supports_markdown_projection(self) -> None:
        result = self._run_file_command(
            "build-structural-beta-bundle",
            BETA_FIXTURE,
            ".md",
            "--format",
            "markdown",
            "--bundle-id",
            "cli-beta-bundle",
        )
        self.assertTrue(result["text"].startswith("# Structural beta evidence bundle"))
        self.assertIn("GNC-D02-C08", result["text"])

    def test_beta_lineage_command_includes_audit(self) -> None:
        result = self._run_file_command("structural-beta-lineage", BETA_FIXTURE)
        self.assertTrue(result["audit"]["passed"])
        self.assertEqual(result["node_count"], 29)
        self.assertEqual(result["edge_count"], 36)

    def test_beta_pipeline_command_publishes_manifest(self) -> None:
        result = self._run_file_command("run-structural-beta-pipeline", BETA_PIPELINE)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["published"])
        self.assertEqual(result["stage_count"], 4)

    def test_beta_commands_are_registered_in_parser(self) -> None:
        parser = build_parser()
        for command in (
            "evaluate-structural-beta-fixture",
            "audit-structural-beta-data",
            "replay-structural-beta-fixtures",
            "structural-beta-quality-gate",
            "evaluate-structural-beta-scenarios",
            "structural-beta-contracts",
            "build-structural-beta-bundle",
            "structural-beta-lineage",
            "run-structural-beta-pipeline",
        ):
            if command == "structural-beta-contracts":
                arguments = [command]
            elif command == "build-structural-beta-bundle":
                arguments = [command, str(BETA_FIXTURE), "--output", "bundle.json"]
            else:
                arguments = [command, str(BETA_FIXTURE)]
            parsed = parser.parse_args(arguments)
            self.assertEqual(parsed.command, command)
