"""CLI integration tests for the Domain 02 structural evidence surfaces."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-public-aggregate.json"
PIPELINE_ACCEPTED = ROOT / "examples" / "structural-pipeline-accepted.json"
PIPELINE_REVIEW = ROOT / "examples" / "structural-pipeline-batch.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class StructuralFixtureCliTests(unittest.TestCase):
    def _run(self, root: Path, name: str, command: str) -> dict[str, object]:
        output = root / f"{name}.json"
        arguments = [command, str(FIXTURE), "--output", str(output)]
        if command == "replay-structural-fixtures":
            arguments = [
                command,
                str(FIXTURE),
                "--required-context-key",
                CONTEXT,
                "--output",
                str(output),
            ]
        self.assertEqual(main(arguments), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_data_fixture_replay_quality_and_scenario_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self._run(root, "data", "audit-structural-data")
            fixture = self._run(root, "fixture", "evaluate-structural-fixture")
            replay = self._run(root, "replay", "replay-structural-fixtures")
            quality = self._run(root, "quality", "structural-quality-gate")
            scenarios = self._run(root, "scenarios", "evaluate-structural-scenarios")
            lineage = self._run(root, "lineage", "structural-lineage")
            self.assertTrue(data["accepted"])
            self.assertTrue(fixture["passed"])
            self.assertTrue(replay["passed"])
            self.assertTrue(quality["passed"])
            self.assertTrue(scenarios["passed"])
            self.assertTrue(lineage["audit"]["passed"])
            self.assertEqual(lineage["node_count"], 29)
            self.assertEqual(lineage["edge_count"], 36)
            self.assertEqual(fixture["check_count"], 95)
            self.assertEqual(scenarios["scenario_count"], 12)
            self.assertEqual(quality["check_count"], 17)

    def test_contract_and_bundle_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts_path = root / "contracts.json"
            bundle_path = root / "bundle.json"
            self.assertEqual(main(["structural-contracts", "--output", str(contracts_path)]), 0)
            self.assertEqual(
                main(
                    [
                        "build-structural-bundle",
                        str(FIXTURE),
                        "--output",
                        str(bundle_path),
                    ]
                ),
                0,
            )
            contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(contracts["contract_count"], 4)
            self.assertTrue(bundle["accepted"])
            self.assertEqual(bundle["entry_count"], 12)
            self.assertNotIn("records", bundle)

    def test_bundle_cli_supports_markdown_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "structural.md"
            csv = root / "structural.csv"
            self.assertEqual(
                main(
                    [
                        "build-structural-bundle",
                        str(FIXTURE),
                        "--output",
                        str(markdown),
                        "--format",
                        "markdown",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "build-structural-bundle",
                        str(FIXTURE),
                        "--output",
                        str(csv),
                        "--format",
                        "csv",
                    ]
                ),
                0,
            )
            self.assertTrue(markdown.read_text(encoding="utf-8").startswith("# Structural"))
            self.assertEqual(len(csv.read_text(encoding="utf-8").splitlines()), 13)

    def test_pipeline_cli_returns_success_for_accepted_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pipeline.json"
            self.assertEqual(
                main(["run-structural-pipeline", str(PIPELINE_ACCEPTED), "--output", str(output)]),
                0,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["accepted"])
            self.assertTrue(report["published"])
            self.assertEqual(report["state"], "accepted")
            self.assertEqual(report["stage_count"], 4)

    def test_pipeline_cli_preserves_review_exit_for_review_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pipeline-review.json"
            self.assertEqual(
                main(["run-structural-pipeline", str(PIPELINE_REVIEW), "--output", str(output)]),
                2,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["accepted"])
            self.assertTrue(report["published"])
            self.assertEqual(report["state"], "review")
            self.assertIn("missing_mate_id", report["issues"])

    def test_help_registers_all_structural_commands(self) -> None:
        parser = __import__("glio_noncode.cli", fromlist=["build_parser"]).build_parser()
        commands = set(parser._subparsers._group_actions[0].choices)
        self.assertTrue(
            {
                "evaluate-structural-fixture",
                "audit-structural-data",
                "replay-structural-fixtures",
                "structural-quality-gate",
                "evaluate-structural-scenarios",
                "structural-contracts",
                "build-structural-bundle",
                "run-structural-pipeline",
                "structural-lineage",
            }.issubset(commands)
        )

    def test_fixture_failure_returns_two_without_silent_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failure.json"
            self.assertEqual(
                main(
                    [
                        "replay-structural-fixtures",
                        str(FIXTURE),
                        str(FIXTURE),
                        "--output",
                        str(output),
                    ]
                ),
                2,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["passed"])
            self.assertIn("duplicate_fixture_identity", report["issue_codes"])


if __name__ == "__main__":
    unittest.main()
