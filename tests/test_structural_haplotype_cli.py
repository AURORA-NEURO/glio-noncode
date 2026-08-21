from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


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


if __name__ == "__main__":
    unittest.main()
