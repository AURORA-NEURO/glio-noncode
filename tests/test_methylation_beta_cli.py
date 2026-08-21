from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"


class MethylationBetaCliTests(unittest.TestCase):
    def test_parse_and_query_methylation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "methylation.tsv"
            output = root / "methylation.json"
            query_output = root / "query.json"
            source.write_text(
                f"chrom\tposition\tbeta\tcontext\n7\t100\t0.8\t{CONTEXT}\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-methylation", str(source), "--output", str(output)]),
                0,
            )
            parsed = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(parsed["records"][0]["position"], 100)
            self.assertEqual(
                main(
                    [
                        "query-methylation-context",
                        str(source),
                        "--chromosome",
                        "7",
                        "--start",
                        "100",
                        "--end",
                        "100",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(query_output),
                    ]
                ),
                0,
            )
            query = json.loads(query_output.read_text(encoding="utf-8"))
            self.assertEqual(query["query"]["state"], "supported")
            self.assertEqual(query["query"]["median_beta"], 0.8)

    def test_cpg_and_methylation_sensitive_motif_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cpg_source = root / "cpg.json"
            cpg_output = root / "cpg-output.json"
            motif_source = root / "motif.json"
            motif_output = root / "motif-output.json"
            cpg_source.write_text(
                json.dumps(
                    {
                        "variant_id": "var-cli-cpg",
                        "reference_sequence": "AAGTT",
                        "alternate_sequence": "ACGTT",
                        "window_start": 99,
                        "chromosome": "7",
                        "context_key": CONTEXT,
                        "methylation_records": [
                            {
                                "record_id": "meth-100",
                                "chromosome": "7",
                                "position": 100,
                                "beta_value": 0.8,
                                "context_key": CONTEXT,
                                "source_id": "methylation-atlas",
                                "source_version": "v1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(["analyze-cpg-change", str(cpg_source), "--output", str(cpg_output)]),
                0,
            )
            cpg = json.loads(cpg_output.read_text(encoding="utf-8"))
            self.assertEqual(cpg["created"][0]["methylation_state"], "methylated")

            motif_source.write_text(
                json.dumps(
                    {
                        "sequence_id": "window-cli-motif",
                        "sequence": "ACGTT",
                        "window_start": 99,
                        "chromosome": "7",
                        "context_key": CONTEXT,
                        "motifs": [
                            {
                                "motif_id": "TF:CG",
                                "name": "CG factor",
                                "consensus": "CG",
                                "source_id": "motif-catalog",
                                "source_version": "v1",
                                "sensitive_positions": [0],
                                "strand_aware": False,
                            }
                        ],
                        "methylation_records": [
                            {
                                "record_id": "meth-100",
                                "chromosome": "7",
                                "position": 100,
                                "beta_value": 0.8,
                                "context_key": CONTEXT,
                                "source_id": "methylation-atlas",
                                "source_version": "v1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "analyze-methylation-motifs",
                        str(motif_source),
                        "--output",
                        str(motif_output),
                    ]
                ),
                0,
            )
            motif = json.loads(motif_output.read_text(encoding="utf-8"))
            self.assertEqual(motif["state"], "supported")
            self.assertEqual(motif["hits"][0]["methylation_state"], "methylated")

    def test_idh_hypermethylation_model_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "idh.json"
            output = root / "idh-output.json"
            target = [
                {
                    "record_id": f"target-{index}",
                    "chromosome": "7",
                    "position": 100 + index,
                    "beta_value": value,
                    "context_key": CONTEXT,
                    "molecular_state": "IDH-mutant",
                    "source_id": "methylation-atlas",
                    "source_version": "v1",
                }
                for index, value in enumerate((0.8, 0.9, 0.7))
            ]
            comparator = [
                {
                    "record_id": f"comparator-{index}",
                    "chromosome": "7",
                    "position": 100 + index,
                    "beta_value": 0.2,
                    "context_key": CONTEXT,
                    "molecular_state": "IDH-wildtype",
                    "source_id": "methylation-atlas",
                    "source_version": "v1",
                }
                for index in range(3)
            ]
            source.write_text(
                json.dumps({"target_records": target, "comparator_records": comparator}),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "model-idh-hypermethylation",
                        str(source),
                        "--model-id",
                        "idh-panel",
                        "--model-version",
                        "v1",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["state"], "supported")
            self.assertTrue(result["hypermethylated"])
            self.assertEqual(result["delta_vs_comparator"], 0.6)


if __name__ == "__main__":
    unittest.main()
