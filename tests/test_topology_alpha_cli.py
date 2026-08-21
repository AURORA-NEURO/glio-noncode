from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"


class TopologyAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_boundary_motif_orientation_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "boundary.json",
                {
                    "records": [
                        {
                            "boundary_id": "b1",
                            "chrom": "7",
                            "boundary_position": 100,
                            "side": "left",
                            "motif_id": "m1",
                            "orientation": "+",
                            "context_key": CONTEXT,
                        },
                        {
                            "boundary_id": "b1",
                            "chrom": "7",
                            "boundary_position": 100,
                            "side": "right",
                            "motif_id": "m2",
                            "orientation": "-",
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["analyze-boundary-motif-orientation", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["relationship_labels"], ["convergent"])

    def test_ctcf_cohesin_disruption_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "ctcf.json",
                {
                    "records": [
                        {
                            "variant_id": "v1",
                            "reference_ctcf": 0.9,
                            "alternate_ctcf": 0.4,
                            "reference_cohesin": 0.8,
                            "alternate_cohesin": 0.5,
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["model-ctcf-cohesin-disruption", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["disruption_label"], "disrupted")

    def test_idh_insulator_dysfunction_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "idh.json",
                {
                    "records": [
                        {
                            "region_id": "r1",
                            "molecular_state": "IDH-mutant",
                            "insulator_score": 0.3,
                        },
                        {
                            "region_id": "r1",
                            "molecular_state": "IDH-wildtype",
                            "insulator_score": 0.8,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["model-idh-insulator-dysfunction", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["label"], "dysfunction_candidate")

    def test_sv_topology_rewiring_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "sv.json",
                {
                    "contacts": [{"edge_id": "e1", "source_node": "n1", "target_node": "n2"}],
                    "events": [
                        {"sv_id": "sv1", "deleted_edge_ids": ["e1"], "gained_edge_ids": ["e2"]}
                    ],
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["simulate-sv-topology-rewiring", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["lost_edge_ids"], ["e1"])
            self.assertEqual(payload["results"][0]["gained_edge_ids"], ["e2"])


if __name__ == "__main__":
    unittest.main()
