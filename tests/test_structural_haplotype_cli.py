from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

ROOT = Path(__file__).resolve().parents[1]
HAPLOTYPE_FIXTURE = ROOT / "examples" / "structural-haplotype-public-aggregate.json"
HAPLOTYPE_PIPELINE = ROOT / "examples" / "structural-haplotype-pipeline-accepted.json"


class StructuralHaplotypeCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_assemble_haplotype_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "phased.json",
                {
                    "records": [
                        {
                            "observation_id": "v1",
                            "sample_id": "S1",
                            "chrom": "7",
                            "pos": 100,
                            "ref": "A",
                            "alt": "T",
                            "GT": "1|0",
                            "PS": "ps1",
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(main(["assemble-haplotype", str(source), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(len(payload["haplotypes"]), 2)

    def test_allele_aware_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "events.json",
                {
                    "records": [
                        {
                            "event_id": "sv1",
                            "sample_id": "S1",
                            "chrom": "7",
                            "start": 10,
                            "end": 20,
                            "alternate": "<DEL>",
                            "GT": "1|0",
                            "allele_index": 1,
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["represent-allele-aware-sv", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["events"][0]["dosage"], 1)

    def test_pangenome_projection_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "queries.json",
                {"queries": [{"query_id": "q1", "chrom": "7", "start": 10, "end": 20}]},
            )
            nodes = self._write(
                root,
                "nodes.json",
                {
                    "nodes": [
                        {"node_id": "n1", "path_id": "p1", "chrom": "7", "start": 1, "end": 30}
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "project-pangenome",
                        str(source),
                        "--nodes",
                        str(nodes),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["matches"][0]["relation"], "contained")

    def test_repeat_mobile_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "queries.json",
                {"queries": [{"query_id": "q1", "chrom": "7", "start": 10, "end": 20}]},
            )
            annotations = self._write(
                root,
                "repeats.json",
                {
                    "annotations": [
                        {
                            "annotation_id": "r1",
                            "chrom": "7",
                            "start": 15,
                            "end": 18,
                            "family": "L1",
                            "class": "LINE",
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "annotate-repeat-mobile",
                        str(source),
                        "--annotations",
                        str(annotations),
                        "--mobile-only",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["hits"][0]["class_name"], "LINE")
            self.assertTrue(payload["hits"][0]["is_mobile"])

    def _run_file_command(self, command: str, source: Path, suffix: str = ".json", *arguments: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / f"output{suffix}"
            self.assertEqual(
                main([command, str(source), *arguments, "--output", str(output)]),
                0,
            )
            if suffix == ".json":
                return json.loads(output.read_text(encoding="utf-8"))
            return {"text": output.read_text(encoding="utf-8")}

    def test_haplotype_fixture_evaluation_command(self) -> None:
        result = self._run_file_command("evaluate-structural-haplotype-fixture", HAPLOTYPE_FIXTURE)
        self.assertTrue(result["passed"])
        self.assertEqual(result["check_count"], 72)
        self.assertEqual(len(result["receipts"]), 12)

    def test_haplotype_data_audit_command(self) -> None:
        result = self._run_file_command("audit-structural-haplotype-data", HAPLOTYPE_FIXTURE)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["positive_count"], 4)
        self.assertEqual(result["control_count"], 8)

    def test_haplotype_replay_quality_and_scenario_commands(self) -> None:
        for command in (
            "replay-structural-haplotype-fixtures",
            "structural-haplotype-quality-gate",
            "evaluate-structural-haplotype-scenarios",
        ):
            result = self._run_file_command(command, HAPLOTYPE_FIXTURE)
            self.assertTrue(result["passed"], command)

    def test_haplotype_contract_manifest_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            self.assertEqual(main(["structural-haplotype-contracts", "--output", str(output)]), 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["contract_count"], 4)
            self.assertEqual(result["schema_version"], "structural-haplotype-contracts-v1")

    def test_haplotype_bundle_command_supports_markdown_projection(self) -> None:
        result = self._run_file_command(
            "build-structural-haplotype-bundle",
            HAPLOTYPE_FIXTURE,
            ".md",
            "--format",
            "markdown",
            "--bundle-id",
            "cli-haplotype-bundle",
        )
        self.assertTrue(result["text"].startswith("# Structural haplotype evidence bundle"))
        self.assertIn("GNC-D02-C12", result["text"])

    def test_haplotype_lineage_command_includes_audit(self) -> None:
        result = self._run_file_command("structural-haplotype-lineage", HAPLOTYPE_FIXTURE)
        self.assertTrue(result["audit"]["passed"])
        self.assertEqual(result["node_count"], 29)
        self.assertEqual(result["edge_count"], 36)

    def test_haplotype_pipeline_command_publishes_manifest(self) -> None:
        result = self._run_file_command("run-structural-haplotype-pipeline", HAPLOTYPE_PIPELINE)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["published"])
        self.assertEqual(result["stage_count"], 4)

    def test_haplotype_commands_are_registered_in_parser(self) -> None:
        from glio_noncode.cli import build_parser

        parser = build_parser()
        for command in (
            "evaluate-structural-haplotype-fixture",
            "audit-structural-haplotype-data",
            "replay-structural-haplotype-fixtures",
            "structural-haplotype-quality-gate",
            "evaluate-structural-haplotype-scenarios",
            "structural-haplotype-contracts",
            "build-structural-haplotype-bundle",
            "structural-haplotype-lineage",
            "run-structural-haplotype-pipeline",
        ):
            if command == "structural-haplotype-contracts":
                arguments = [command]
            elif command == "build-structural-haplotype-bundle":
                arguments = [command, str(HAPLOTYPE_FIXTURE), "--output", "bundle.json"]
            else:
                arguments = [command, str(HAPLOTYPE_FIXTURE)]
            parsed = parser.parse_args(arguments)
            self.assertEqual(parsed.command, command)


if __name__ == "__main__":
    unittest.main()
