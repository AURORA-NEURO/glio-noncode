from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/reference-annotation-public-aggregate.json"


class ReferenceAnnotationCliTests(unittest.TestCase):
    def test_all_c05_c08_commands_are_registered(self) -> None:
        commands = {
            "evaluate-reference-annotation-fixture",
            "audit-reference-annotation-data",
            "replay-reference-annotation-fixtures",
            "reference-annotation-quality-gate",
            "evaluate-reference-annotation-scenarios",
            "reference-annotation-contracts",
            "build-reference-annotation-bundle",
            "reference-annotation-lineage",
            "reference-annotation-reconciliation",
            "run-reference-annotation-pipeline",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "commands.json"
            self.assertEqual(main(["reference-annotation-contracts", "--output", str(output)]), 0)
            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                {entry["operation"] for entry in manifest["contracts"]},
                {
                    "gencode_transcript_catalog",
                    "mane_transcript_catalog",
                    "regulatory_ontology_catalog",
                    "disease_ontology_mapping",
                },
            )
        self.assertEqual(len(commands), 10)

    def test_data_evaluation_replay_quality_and_scenario_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command, name in (
                ("audit-reference-annotation-data", "data"),
                ("evaluate-reference-annotation-fixture", "evaluation"),
                ("replay-reference-annotation-fixtures", "replay"),
                ("reference-annotation-quality-gate", "quality"),
                ("evaluate-reference-annotation-scenarios", "scenarios"),
            ):
                output = root / f"{name}.json"
                self.assertEqual(main([command, str(FIXTURE), "--output", str(output)]), 0)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertTrue(payload.get("accepted"))

    def test_bundle_command_supports_json_csv_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for selected, suffix in (("json", ".json"), ("csv", ".csv"), ("markdown", ".md")):
                output = root / f"bundle{suffix}"
                self.assertEqual(
                    main(
                        [
                            "build-reference-annotation-bundle",
                            str(FIXTURE),
                            "--output",
                            str(output),
                            "--format",
                            selected,
                            "--accepted-only",
                        ]
                    ),
                    0,
                )
                self.assertTrue(output.read_text(encoding="utf-8"))

    def test_lineage_and_reconciliation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command, name in (
                ("reference-annotation-lineage", "lineage"),
                ("reference-annotation-reconciliation", "reconciliation"),
            ):
                output = root / f"{name}.json"
                self.assertEqual(main([command, str(FIXTURE), "--output", str(output)]), 0)
                self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["accepted"])

    def test_pipeline_command_publishes_accepted_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pipeline.json"
            request = ROOT / "examples/reference-annotation-pipeline-accepted.json"
            self.assertEqual(
                main(["run-reference-annotation-pipeline", str(request), "--output", str(output)]),
                0,
            )
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["published"])

    def test_pipeline_command_returns_nonzero_for_context_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pipeline.json"
            request = ROOT / "examples/reference-annotation-pipeline-review.json"
            self.assertEqual(
                main(["run-reference-annotation-pipeline", str(request), "--output", str(output)]),
                2,
            )
            self.assertFalse(json.loads(output.read_text(encoding="utf-8"))["published"])

    def test_release_command_writes_publishable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.json"
            self.assertEqual(
                main(["build-reference-annotation-release", str(FIXTURE), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "published")
            self.assertTrue(payload["publishable"])

    def test_commands_do_not_emit_input_text_in_sanitized_quality_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "quality.json"
            self.assertEqual(
                main(["reference-annotation-quality-gate", str(FIXTURE), "--output", str(output)]),
                0,
            )
            payload = output.read_text(encoding="utf-8")
            self.assertNotIn("input_text", payload)
