from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class AtlasAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_harmonize_open_chromatin_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "atac.json",
                {
                    "records": [
                        {
                            "id": "a1",
                            "chrom": "7",
                            "start": 100,
                            "end": 120,
                            "signal": 4,
                            "replicate": "r1",
                            "caller": "caller-a",
                            "context_key": CONTEXT,
                        },
                        {
                            "id": "a2",
                            "chrom": "7",
                            "start": 100,
                            "end": 120,
                            "signal": 4.1,
                            "replicate": "r2",
                            "caller": "caller-a",
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "harmonize-open-chromatin",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["intervals"][0]["replicate_ids"], ["r1", "r2"])

    def test_harmonize_methylation_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "methylation.json",
                {
                    "records": [
                        {
                            "id": "m1",
                            "chrom": "1",
                            "start": 200,
                            "end": 200,
                            "methylated_count": 8,
                            "total_count": 10,
                            "replicate": "r1",
                            "context_key": CONTEXT,
                        },
                        {
                            "id": "m2",
                            "chrom": "1",
                            "start": 200,
                            "end": 200,
                            "methylated_count": 6,
                            "total_count": 10,
                            "replicate": "r2",
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["harmonize-methylation", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["intervals"][0]["total_count"], 20)

    def test_classify_regulatory_role_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "roles.json",
                {
                    "elements": [
                        {
                            "element_id": "el-1",
                            "chrom": "7",
                            "start": 100,
                            "end": 110,
                            "promoter_score": 0.1,
                            "enhancer_score": 0.8,
                            "silencer_score": 0.1,
                            "open_chromatin_signal": 3,
                            "contact_support": 0.7,
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "classify-regulatory-role",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["classifications"][0]["roles"], ["enhancer"])

    def test_build_super_enhancer_atlas_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "enhancers.json",
                {
                    "intervals": [
                        {
                            "enhancer_id": "e1",
                            "chrom": "7",
                            "start": 100,
                            "end": 110,
                            "signal": 5,
                            "context_key": CONTEXT,
                        },
                        {
                            "enhancer_id": "e2",
                            "chrom": "7",
                            "start": 120,
                            "end": 130,
                            "signal": 4,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "build-super-enhancer-atlas",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--minimum-constituents",
                        "2",
                        "--merge-gap-bp",
                        "10",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "partial")
            self.assertEqual(len(payload["candidates"]), 1)


if __name__ == "__main__":
    unittest.main()
