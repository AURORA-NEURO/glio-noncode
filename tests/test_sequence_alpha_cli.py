from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class SequenceAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_predict_nucleosome_propensity_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "nucleosome.json",
                {"records": [{"sequence_id": "n1", "sequence": "AA" * 74}]},
            )
            output = root / "out.json"
            self.assertEqual(
                main(["predict-nucleosome-propensity", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["windows"][0]["positioning_label"], "favored")

    def test_scan_splice_regulatory_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "splice.json",
                {
                    "context_key": CONTEXT,
                    "records": [
                        {
                            "sequence_id": "s1",
                            "reference_sequence": "AACGTAA",
                            "alternate_sequence": "AACATAA",
                        }
                    ],
                    "motifs": [
                        {
                            "motif_id": "donor",
                            "name": "donor",
                            "consensus": "GT",
                            "role": "donor",
                            "source_id": "splice-cli",
                            "source_version": "v1",
                            "strand_aware": False,
                        }
                    ],
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["scan-splice-regulatory", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["windows"][0]["disrupted_hits"][0]["role"], "donor")

    def test_scan_utr_regulatory_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "utr.json",
                {
                    "records": [
                        {
                            "utr_id": "u1",
                            "region": "5utr",
                            "sequence": "CCCATGAAATAA",
                            "context_key": CONTEXT,
                        }
                    ],
                    "motifs": [
                        {
                            "motif_id": "uorf",
                            "name": "uORF start",
                            "consensus": "ATG",
                            "element_kind": "uorf_start",
                            "region": "5utr",
                            "source_id": "utr-cli",
                            "source_version": "v1",
                            "strand_aware": False,
                        }
                    ],
                },
            )
            output = root / "out.json"
            self.assertEqual(main(["scan-utr-regulatory", str(source), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["windows"][0]["upstream_orfs"]), 1)

    def test_evaluate_promoter_grammar_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "promoter.json",
                {
                    "records": [{"promoter_id": "p1", "sequence": "AAAATATAAAACAGG"}],
                    "motifs": [
                        {
                            "motif_id": "tata",
                            "name": "TATA",
                            "consensus": "TATA",
                            "element_kind": "tata",
                            "source_id": "promoter-cli",
                            "source_version": "v1",
                            "strand_aware": False,
                        },
                        {
                            "motif_id": "inr",
                            "name": "Inr",
                            "consensus": "CA",
                            "element_kind": "initiator",
                            "source_id": "promoter-cli",
                            "source_version": "v1",
                            "strand_aware": False,
                        },
                    ],
                    "rules": [
                        {
                            "rule_id": "tata-inr",
                            "motif_a": "tata",
                            "motif_b": "inr",
                            "minimum_spacing": 2,
                            "maximum_spacing": 4,
                            "allowed_orientations": ["same"],
                        }
                    ],
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["evaluate-promoter-grammar", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["evaluations"][0]["weighted_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
