from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class ReferenceBetaCliTests(unittest.TestCase):
    def test_parse_gencode_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "transcripts.gtf"
            output = root / "transcripts.json"
            source.write_text(
                '7\tGENCODE\ttranscript\t100\t500\t.\t+\t.\t'
                'gene_id "GENE1"; transcript_id "TX1.2"; gene_name "GENE1";\n',
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-gencode", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["records"][0]["versioned_id"], "TX1.2")

    def test_parse_mane_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mane.tsv"
            output = root / "mane.json"
            source.write_text(
                "ensembl_transcript_id\trefseq_transcript_id\tgene_id\tmane_status\n"
                "TX1\tNM_1\tGENE1\tMANE Select\n",
                encoding="utf-8",
            )
            self.assertEqual(main(["parse-mane", str(source), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["records"][0]["mane_status"], "MANE Select")

    def test_normalize_regulatory_term_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            query = root / "query.json"
            catalog = root / "ontology.json"
            output = root / "result.json"
            query.write_text(json.dumps({"term_id": "RO:1"}), encoding="utf-8")
            catalog.write_text(
                json.dumps(
                    {
                        "terms": [
                            {
                                "term_id": "RO:1",
                                "label": "enhancer",
                                "definition": "declared enhancer",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "normalize-regulatory-term",
                        str(query),
                        "--catalog",
                        str(catalog),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["normalization"]["state"], "supported")

    def test_map_disease_term_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            query = root / "query.json"
            catalog = root / "disease.json"
            output = root / "result.json"
            query.write_text(json.dumps({"source_term_id": "SRC:1"}), encoding="utf-8")
            catalog.write_text(
                json.dumps(
                    {
                        "mappings": [
                            {
                                "source_term_id": "SRC:1",
                                "source_label": "glioma",
                                "target_term_id": "MONDO:1",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "map-disease-term",
                        str(query),
                        "--catalog",
                        str(catalog),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["mapping"]["state"], "supported")

