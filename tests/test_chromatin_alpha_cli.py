from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"


class ChromatinAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_segment_chromatin_state_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "segments.json",
                {
                    "records": [
                        {
                            "id": "c1",
                            "chrom": "7",
                            "start": 100,
                            "end": 120,
                            "signal": 0.9,
                            "replicate": "r1",
                            "context_key": CONTEXT,
                        },
                        {
                            "id": "c2",
                            "chrom": "7",
                            "start": 100,
                            "end": 120,
                            "signal": 0.8,
                            "replicate": "r2",
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["segment-chromatin-state", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["segments"][0]["state_label"], "open")

    def test_analyze_allele_specific_chromatin_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "alleles.json",
                {
                    "records": [
                        {
                            "variant_id": "v1",
                            "assay": "ATAC",
                            "reference_signal": 2,
                            "alternate_signal": 3,
                            "replicate": "r1",
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["analyze-allele-specific-chromatin", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["direction"], "increased")

    def test_deconvolve_epigenomic_purity_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "purity.json",
                {
                    "markers": [
                        {
                            "marker_id": "m1",
                            "observed_signal": 0.6,
                            "tumor_signal": 1,
                            "normal_signal": 0,
                            "context_key": CONTEXT,
                        },
                        {
                            "marker_id": "m2",
                            "observed_signal": 0.3,
                            "tumor_signal": 0.5,
                            "normal_signal": 0,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["deconvolve-epigenomic-purity", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["aggregate_purity"], 0.6)

    def test_correct_batch_cell_composition_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "correction.json",
                {
                    "target_composition": {"tumor": 0.5, "normal": 0.5},
                    "records": [
                        {
                            "feature_id": "f1",
                            "batch_id": "b1",
                            "raw_signal": 1,
                            "batch_offset": 0.1,
                            "cell_composition": {"tumor": 0.8, "normal": 0.2},
                            "composition_coefficients": {"tumor": 0.5, "normal": -0.5},
                            "context_key": CONTEXT,
                        }
                    ],
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["correct-batch-cell-composition", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["corrections"][0]["corrected_signal"], 0.6)


if __name__ == "__main__":
    unittest.main()
