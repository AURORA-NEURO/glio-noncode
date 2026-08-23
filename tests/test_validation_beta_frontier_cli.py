"""CLI contract tests for the Domain 13 C05-C12 frontier."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class ValidationBetaFrontierCliTests(unittest.TestCase):
    def test_fixture_and_data_commands_emit_closed_public_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            audit = Path(directory) / "audit.json"
            self.assertEqual(main(["validation-beta-frontier-fixture", "--output", str(fixture)]), 0)
            self.assertEqual(main(["validation-beta-frontier-data", "--output", str(audit)]), 0)
            self.assertEqual(len(json.loads(fixture.read_text(encoding="utf-8"))["records"]), 32)
            self.assertTrue(json.loads(audit.read_text(encoding="utf-8"))["accepted"])

    def test_contract_schema_and_evaluation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contracts = Path(directory) / "contracts.json"
            schema = Path(directory) / "schema.json"
            evaluation = Path(directory) / "evaluation.json"
            self.assertEqual(main(["validation-beta-frontier-contracts", "--output", str(contracts)]), 0)
            self.assertEqual(main(["validation-beta-frontier-schema", "--output", str(schema)]), 0)
            self.assertEqual(main(["validation-beta-frontier-evaluate", "--output", str(evaluation)]), 0)
            self.assertEqual(json.loads(contracts.read_text(encoding="utf-8"))["contract_count"], 8)
            self.assertEqual(len(json.loads(schema.read_text(encoding="utf-8"))["operations"]), 8)
            self.assertTrue(json.loads(evaluation.read_text(encoding="utf-8"))["accepted"])

    def test_quality_replay_release_and_bundle_commands(self) -> None:
        commands = ("validation-beta-frontier-quality", "validation-beta-frontier-replay", "validation-beta-frontier-release", "validation-beta-frontier-bundle", "run-validation-beta-frontier-pipeline")
        with tempfile.TemporaryDirectory() as directory:
            for command in commands:
                output = Path(directory) / f"{command}.json"
                self.assertEqual(main([command, "--output", str(output)]), 0)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertTrue(payload.get("accepted", payload.get("ready", payload.get("deterministic", False))))

    def test_supporting_review_commands_emit_structured_outputs(self) -> None:
        commands = ("validation-beta-frontier-metrics", "validation-beta-frontier-lineage", "validation-beta-frontier-policy", "validation-beta-frontier-reconciliation", "validation-beta-frontier-review", "validation-beta-frontier-scenarios", "validation-beta-frontier-depth", "validation-beta-frontier-artifacts", "validation-beta-frontier-controls", "validation-beta-frontier-operational", "validation-beta-frontier-integrity", "validation-beta-frontier-failures", "validation-beta-frontier-runbook", "validation-beta-frontier-summary")
        with tempfile.TemporaryDirectory() as directory:
            for command in commands:
                output = Path(directory) / f"{command}.json"
                self.assertEqual(main([command, "--output", str(output)]), 0)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)

    def test_report_formats_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "review.csv"
            markdown_path = Path(directory) / "review.md"
            json_path = Path(directory) / "review.json"
            self.assertEqual(main(["validation-beta-frontier-report", "--format", "csv", "--output", str(csv_path)]), 0)
            self.assertEqual(main(["validation-beta-frontier-report", "--format", "markdown", "--output", str(markdown_path)]), 0)
            self.assertEqual(main(["validation-beta-frontier-report", "--format", "json", "--output", str(json_path)]), 0)
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("record_id,operation"))
            self.assertIn("# Validation-beta frontier review", markdown_path.read_text(encoding="utf-8"))
            self.assertTrue(json.loads(json_path.read_text(encoding="utf-8"))["accepted"])

    def test_serialized_fixture_input_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            evaluation = Path(directory) / "evaluation.json"
            self.assertEqual(main(["validation-beta-frontier-fixture", "--output", str(fixture)]), 0)
            self.assertEqual(main(["validation-beta-frontier-evaluate", "--input", str(fixture), "--output", str(evaluation)]), 0)
            self.assertTrue(json.loads(evaluation.read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()
