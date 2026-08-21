from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


class LinkGraphBetaCliTests(unittest.TestCase):
    def test_parse_activity_contact_link_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "activity.tsv"
            output = root / "activity.json"
            source.write_text(
                "evidence_id\tvariant_id\telement_id\tgene_id\tactivity_signal\tcontact_signal\tcontext\n"
                f"abc-1\tv1\tenh-1\tGENE1\t0.8\t5\t{CONTEXT}\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-activity-contact-link", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["observations"][0]["support"], 0.4)

    def test_coaccessibility_qtl_and_allele_integrator_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coaccess_source = root / "coaccess.json"
            coaccess_output = root / "coaccess-output.json"
            coaccess_source.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "evidence_id": "co-1",
                                "variant_id": "v1",
                                "element_id": "enh-1",
                                "gene_id": "GENE1",
                                "score": 0.7,
                                "context_key": CONTEXT,
                                "source_id": "coaccess",
                                "source_version": "v1",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "link-coaccessibility",
                        str(coaccess_source),
                        "--context-key",
                        CONTEXT,
                        "--variant-id",
                        "v1",
                        "--output",
                        str(coaccess_output),
                    ]
                ),
                0,
            )
            coaccess = json.loads(coaccess_output.read_text(encoding="utf-8"))
            self.assertEqual(coaccess["state"], "partial")

            qtl_source = root / "qtl.json"
            qtl_output = root / "qtl-output.json"
            qtl_source.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "evidence_id": "qtl-1",
                                "variant_id": "v1",
                                "element_id": "enh-1",
                                "gene_id": "GENE1",
                                "effect_size": 0.4,
                                "q_value": 0.001,
                                "context_key": CONTEXT,
                                "source_id": "qtl",
                                "source_version": "v2",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "link-molecular-qtl",
                        str(qtl_source),
                        "--context-key",
                        CONTEXT,
                        "--variant-id",
                        "v1",
                        "--output",
                        str(qtl_output),
                    ]
                ),
                0,
            )
            qtl = json.loads(qtl_output.read_text(encoding="utf-8"))
            self.assertEqual(qtl["state"], "partial")

            allele_source = root / "allele.json"
            allele_output = root / "allele-output.json"
            allele_source.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "evidence_id": "gain",
                                "variant_id": "v1",
                                "element_id": "enh-1",
                                "gene_id": "GENE1",
                                "direction": "gain",
                                "support": 0.8,
                                "confidence": 0.9,
                                "context_key": CONTEXT,
                                "source_id": "sequence",
                                "source_version": "v1",
                            },
                            {
                                "evidence_id": "loss",
                                "variant_id": "v1",
                                "element_id": "enh-1",
                                "gene_id": "GENE1",
                                "direction": "loss",
                                "support": 0.7,
                                "confidence": 0.9,
                                "context_key": CONTEXT,
                                "source_id": "chromatin",
                                "source_version": "v1",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "integrate-allele-specific-links",
                        str(allele_source),
                        "--context-key",
                        CONTEXT,
                        "--variant-id",
                        "v1",
                        "--output",
                        str(allele_output),
                    ]
                ),
                0,
            )
            allele = json.loads(allele_output.read_text(encoding="utf-8"))
            self.assertEqual(allele["state"], "contradictory")


if __name__ == "__main__":
    unittest.main()
