"""CLI integration tests for the Domain 01 intake evidence commands."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "intake-public-aggregate.json"
PIPELINE_ACCEPTED = ROOT / "examples" / "intake-pipeline-accepted.json"
PIPELINE_REVIEW = ROOT / "examples" / "intake-pipeline-batch.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class IntakeFixtureCliTests(unittest.TestCase):
    def _run(self, root: Path, name: str, command: str) -> dict[str, object]:
        output = root / f"{name}.json"
        arguments = [command, str(FIXTURE), "--output", str(output)]
        if command == "replay-intake-fixtures":
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
            data = self._run(root, "data", "audit-intake-data")
            fixture = self._run(root, "fixture", "evaluate-intake-fixture")
            replay = self._run(root, "replay", "replay-intake-fixtures")
            quality = self._run(root, "quality", "intake-quality-gate")
            scenarios = self._run(root, "scenarios", "evaluate-intake-scenarios")
            self.assertTrue(data["accepted"])
            self.assertTrue(fixture["passed"])
            self.assertTrue(replay["passed"])
            self.assertTrue(quality["passed"])
            self.assertTrue(scenarios["passed"])
            self.assertEqual(fixture["check_count"], 33)
            self.assertEqual(scenarios["scenario_count"], 12)

    def test_contract_and_bundle_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts_path = root / "contracts.json"
            bundle_path = root / "bundle.json"
            self.assertEqual(main(["intake-contracts", "--output", str(contracts_path)]), 0)
            self.assertEqual(
                main(
                    [
                        "build-intake-bundle",
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

    def test_bundle_cli_supports_markdown_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "intake.md"
            csv = root / "intake.csv"
            self.assertEqual(
                main(
                    [
                        "build-intake-bundle",
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
                        "build-intake-bundle",
                        str(FIXTURE),
                        "--output",
                        str(csv),
                        "--format",
                        "csv",
                    ]
                ),
                0,
            )
            self.assertTrue(markdown.read_text(encoding="utf-8").startswith("# Intake"))
            self.assertEqual(len(csv.read_text(encoding="utf-8").splitlines()), 13)

    def test_pipeline_cli_returns_success_for_an_accepted_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pipeline.json"
            self.assertEqual(
                main(["run-intake-pipeline", str(PIPELINE_ACCEPTED), "--output", str(output)]),
                0,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["accepted"])
            self.assertTrue(report["published"])
            self.assertEqual(report["state"], "accepted")
            self.assertEqual(report["stage_count"], 4)
            self.assertEqual(report["accepted_count"], 1)
            self.assertNotIn("records", report["bundle"])

    def test_pipeline_cli_preserves_review_exit_for_partial_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pipeline-review.json"
            self.assertEqual(
                main(["run-intake-pipeline", str(PIPELINE_REVIEW), "--output", str(output)]),
                2,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["accepted"])
            self.assertTrue(report["published"])
            self.assertEqual(report["state"], "review")
            self.assertEqual(report["blocked_record_ids"], ["pipeline-review-sequence"])

    def test_help_registers_all_intake_commands(self) -> None:
        parser = __import__("glio_noncode.cli", fromlist=["build_parser"]).build_parser()
        commands = set(parser._subparsers._group_actions[0].choices)
        self.assertTrue(
            {
                "evaluate-intake-fixture",
                "audit-intake-data",
                "replay-intake-fixtures",
                "intake-quality-gate",
                "evaluate-intake-scenarios",
                "intake-contracts",
                "build-intake-bundle",
                "run-intake-pipeline",
            }.issubset(commands)
        )


if __name__ == "__main__":
    unittest.main()
