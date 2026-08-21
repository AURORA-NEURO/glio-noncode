from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "specimen-lineage-public-aggregate.json"
PIPELINE = ROOT / "examples" / "specimen-lineage-pipeline-accepted.json"


class SpecimenLineageCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_multi_region_lineage_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "regions.json",
                {
                    "records": [
                        {
                            "region_id": "r1",
                            "sample_id": "s1",
                            "subject_id": "u1",
                            "region_label": "primary",
                            "relationship": "root",
                        },
                        {
                            "region_id": "r2",
                            "sample_id": "s2",
                            "subject_id": "u1",
                            "region_label": "region-2",
                            "parent_region_id": "r1",
                            "relationship": "derived",
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["resolve-multi-region-lineage", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["lineages"][0]["roots"], ["r1"])

    def test_longitudinal_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "specimens.json",
                {
                    "records": [
                        {
                            "specimen_id": "s1",
                            "sample_id": "a",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-01-01",
                        },
                        {
                            "specimen_id": "s2",
                            "sample_id": "b",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-02-01",
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["link-longitudinal-specimens", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["links"][0]["ordering_basis"], "ordered_time")

    def test_primary_recurrence_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "phases.json",
                {
                    "records": [
                        {
                            "specimen_id": "s1",
                            "sample_id": "a",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-01-01",
                            "phase": "primary",
                        },
                        {
                            "specimen_id": "s2",
                            "sample_id": "b",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-02-01",
                            "phase": "recurrence",
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["map-primary-recurrence", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                [item["phase"] for item in payload["assignments"]], ["primary", "recurrence"]
            )

    def test_treatment_context_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "specimens.json",
                {
                    "records": [
                        {
                            "specimen_id": "s1",
                            "sample_id": "a",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-02-01",
                        }
                    ]
                },
            )
            exposures = self._write(
                root,
                "exposures.json",
                {
                    "exposures": [
                        {
                            "exposure_id": "e1",
                            "subject_id": "u1",
                            "therapy_id": "drug-a",
                            "start_time": "2024-01-01",
                            "end_time": "2024-03-01",
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "contextualize-treatment",
                        str(source),
                        "--exposures",
                        str(exposures),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["contexts"][0]["relation"], "on_treatment")

    def _run_json(self, command: str, source: Path, *arguments: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.json"
            self.assertEqual(main([command, str(source), *arguments, "--output", str(output)]), 0)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_fixture_and_data_commands(self) -> None:
        evaluation = self._run_json("evaluate-specimen-lineage-fixture", FIXTURE)
        self.assertTrue(evaluation["passed"])
        self.assertEqual(len(evaluation["receipts"]), 12)
        audit = self._run_json("audit-specimen-lineage-data", FIXTURE)
        self.assertTrue(audit["accepted"])
        self.assertEqual(audit["positive_count"], 4)
        self.assertEqual(audit["control_count"], 8)

    def test_replay_quality_and_scenario_commands(self) -> None:
        for command in (
            "replay-specimen-lineage-fixtures",
            "specimen-lineage-quality-gate",
            "evaluate-specimen-lineage-scenarios",
        ):
            result = self._run_json(command, FIXTURE)
            self.assertTrue(result["passed"], command)

    def test_contract_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(main(["specimen-lineage-contracts", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["contract_count"], 4)
            self.assertEqual(
                payload["contracts"][0]["contract_version"], "specimen-lineage-contract-v1"
            )

    def test_bundle_command_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.md"
            self.assertEqual(
                main(
                    [
                        "build-specimen-lineage-bundle",
                        str(FIXTURE),
                        "--output",
                        str(output),
                        "--format",
                        "markdown",
                    ]
                ),
                0,
            )
            text = output.read_text(encoding="utf-8")
            self.assertIn("# specimen-lineage-c09-c12", text)
            self.assertIn("positive-region-branching", text)

    def test_lineage_and_pipeline_commands(self) -> None:
        graph = self._run_json("specimen-lineage-lineage", FIXTURE)
        self.assertTrue(graph["audit"]["passed"])
        self.assertEqual(graph["node_count"], 29)
        reconciliation = self._run_json("specimen-lineage-reconciliation", FIXTURE)
        self.assertTrue(reconciliation["audit"]["passed"])
        self.assertEqual(reconciliation["entry_count"], 12)
        pipeline = self._run_json("run-specimen-lineage-pipeline", PIPELINE)
        self.assertTrue(pipeline["published"])
        self.assertEqual(len(pipeline["stage_receipts"]), 4)

    def test_all_commands_are_parser_registered(self) -> None:
        parser = build_parser()
        commands = (
            "evaluate-specimen-lineage-fixture",
            "audit-specimen-lineage-data",
            "replay-specimen-lineage-fixtures",
            "specimen-lineage-quality-gate",
            "evaluate-specimen-lineage-scenarios",
            "specimen-lineage-contracts",
            "build-specimen-lineage-bundle",
            "specimen-lineage-lineage",
            "specimen-lineage-reconciliation",
            "run-specimen-lineage-pipeline",
        )
        for command in commands:
            arguments = [command]
            if command == "specimen-lineage-contracts":
                arguments += []
            elif command == "build-specimen-lineage-bundle":
                arguments += [str(FIXTURE), "--output", "bundle.json"]
            elif command == "run-specimen-lineage-pipeline":
                arguments += [str(PIPELINE)]
            else:
                arguments += [str(FIXTURE)]
            self.assertEqual(parser.parse_args(arguments).command, command)


if __name__ == "__main__":
    unittest.main()
