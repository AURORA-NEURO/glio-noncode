from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class AtlasBetaCliTests(unittest.TestCase):
    def test_query_state_atlas_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "state.json"
            output = root / "query.json"
            source.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "element_id": "enh-1",
                                "chrom": "7",
                                "start": 99,
                                "end": 120,
                                "molecular_state": "IDH-mutant",
                                "context_key": CONTEXT,
                                "assay": "ATAC",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "query-state-atlas",
                        str(source),
                        "--molecular-state",
                        "IDH-mutant",
                        "--chromosome",
                        "7",
                        "--start",
                        "100",
                        "--end",
                        "120",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["query"]["state"], "supported")
            self.assertEqual(payload["query"]["matches"][0]["element_id"], "enh-1")

    def test_harmonize_histone_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "histone.tsv"
            output = root / "histone.json"
            source.write_text(
                "chrom\tstart\tend\tmark\tsignal\treplicate_id\tcontext_key\n"
                f"7\t99\t120\tH3K27ac\t4\trep-1\t{CONTEXT}\n"
                f"7\t99\t120\tH3K27ac\t5\trep-2\t{CONTEXT}\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "harmonize-histone",
                        str(source),
                        "--spread-tolerance",
                        "2",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["intervals"][0]["median_signal"], 4.5)
