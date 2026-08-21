from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/reference-governance-public-aggregate.json"
PIPELINE = ROOT / "examples/reference-governance-pipeline-accepted.json"


class ReferenceGovernanceCliTests(unittest.TestCase):
    def test_contract_command_exposes_all_c09_c12_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(main(["reference-governance-contracts", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                {item["operation"] for item in payload["contracts"]},
                {
                    "gene_alias_version_resolution",
                    "population_frequency_adaptation",
                    "reference_snapshot_manifest",
                    "license_use_restriction",
                },
            )

    def test_data_evaluation_replay_quality_and_scenarios(self) -> None:
        commands = (
            "audit-reference-governance-data",
            "evaluate-reference-governance-fixture",
            "replay-reference-governance-fixtures",
            "reference-governance-quality-gate",
            "evaluate-reference-governance-scenarios",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in commands:
                output = root / f"{command}.json"
                self.assertEqual(main([command, str(FIXTURE), "--output", str(output)]), 0)
                self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["accepted"])

    def test_bundle_command_supports_three_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for selected, suffix in (("json", ".json"), ("csv", ".csv"), ("markdown", ".md")):
                output = root / f"bundle{suffix}"
                self.assertEqual(
                    main(
                        [
                            "build-reference-governance-bundle",
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

    def test_lineage_reconciliation_and_pipeline_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ("reference-governance-lineage", "reference-governance-reconciliation"):
                output = root / f"{command}.json"
                self.assertEqual(main([command, str(FIXTURE), "--output", str(output)]), 0)
                self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["accepted"])
            output = root / "pipeline.json"
            self.assertEqual(
                main(["run-reference-governance-pipeline", str(PIPELINE), "--output", str(output)]),
                0,
            )
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["published"])

    def test_pipeline_command_returns_nonzero_for_context_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "fixture": {"fixture": "default_reference_governance_fixture"},
                        "expected_context_key": "wrong",
                    }
                ),
                encoding="utf-8",
            )
            output = root / "pipeline.json"
            self.assertEqual(
                main(["run-reference-governance-pipeline", str(request), "--output", str(output)]),
                2,
            )
            self.assertFalse(json.loads(output.read_text(encoding="utf-8"))["published"])

    def test_release_command_writes_publishable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.json"
            self.assertEqual(
                main(["build-reference-governance-release", str(FIXTURE), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "published")
            self.assertTrue(payload["publishable"])

    def test_quality_output_does_not_copy_payload_collections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "quality.json"
            self.assertEqual(
                main(["reference-governance-quality-gate", str(FIXTURE), "--output", str(output)]),
                0,
            )
            text = output.read_text(encoding="utf-8")
            self.assertNotIn('"records"', text)
            self.assertNotIn('"restrictions"', text)
            self.assertNotIn('"resources"', text)


if __name__ == "__main__":
    unittest.main()
