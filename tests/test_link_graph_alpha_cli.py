from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


class LinkGraphAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_crispr_parse_and_link_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "crispr.json",
                {
                    "observations": [
                        {
                            "evidence_id": "cr-1",
                            "variant_id": "v1",
                            "element_id": "enh-1",
                            "gene_id": "GENE1",
                            "perturbation_mode": "CRISPRi",
                            "direction": "repressing",
                            "effect_size": -0.6,
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            parsed = root / "crispr-parsed.json"
            self.assertEqual(
                main(
                    [
                        "parse-crispr-perturbation-links",
                        str(source),
                        "--source-id",
                        "crispr",
                        "--output",
                        str(parsed),
                    ]
                ),
                0,
            )
            parsed_payload = json.loads(parsed.read_text(encoding="utf-8"))
            self.assertAlmostEqual(parsed_payload["observations"][0]["bounded_support"], 0.6)
            linked = root / "crispr-linked.json"
            self.assertEqual(
                main(
                    [
                        "link-crispr-perturbations",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--variant-id",
                        "v1",
                        "--output",
                        str(linked),
                    ]
                ),
                0,
            )
            linked_payload = json.loads(linked.read_text(encoding="utf-8"))
            self.assertEqual(linked_payload["state"], "partial")

    def test_contact_parse_and_link_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "contacts.json",
                {
                    "observations": [
                        {
                            "evidence_id": "c-1",
                            "variant_id": "v1",
                            "element_id": "enh-1",
                            "gene_id": "GENE1",
                            "contact_signal": 4.0,
                            "contact_scale": 10.0,
                            "resolution_bp": 5000,
                            "assay_kind": "hic",
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            parsed = root / "contacts-parsed.json"
            self.assertEqual(
                main(
                    [
                        "parse-3d-contact-links",
                        str(source),
                        "--source-id",
                        "hic",
                        "--output",
                        str(parsed),
                    ]
                ),
                0,
            )
            payload = json.loads(parsed.read_text(encoding="utf-8"))
            self.assertAlmostEqual(payload["observations"][0]["normalized_contact"], 0.4)
            linked = root / "contacts-linked.json"
            self.assertEqual(
                main(
                    [
                        "link-3d-contacts",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(linked),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(linked.read_text(encoding="utf-8"))["state"], "partial")

    def test_promoter_tethering_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "tether.json",
                {
                    "observations": [
                        {
                            "observation_id": "t-1",
                            "variant_id": "v1",
                            "element_id": "enh-1",
                            "gene_id": "GENE1",
                            "distance_bp": 1000,
                            "contact_support": 0.8,
                            "promoter_activity": 0.8,
                            "promoter_overlap": True,
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            output = root / "tether-output.json"
            self.assertEqual(
                main(
                    [
                        "model-promoter-tethering",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--minimum-score",
                        "0.3",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["tier"], "promoter_overlap")

    def test_multi_gene_graph_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "graph.json",
                {
                    "evidence": [
                        {
                            "evidence_id": "contact-1",
                            "variant_id": "v1",
                            "element_id": "enh-1",
                            "gene_id": "GENE1",
                            "link_type": "contact",
                            "context_key": CONTEXT,
                            "source_id": "hic",
                            "source_version": "v1",
                            "support": 0.8,
                            "confidence": 0.9,
                        },
                        {
                            "evidence_id": "coaccess-1",
                            "variant_id": "v1",
                            "element_id": "enh-1",
                            "gene_id": "GENE1",
                            "link_type": "coaccessibility",
                            "context_key": CONTEXT,
                            "source_id": "coaccess",
                            "source_version": "v1",
                            "support": 0.7,
                            "confidence": 0.8,
                        },
                    ]
                },
            )
            output = root / "graph-output.json"
            self.assertEqual(
                main(
                    [
                        "build-multi-gene-element-graph",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--graph-id",
                        "cli-graph",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["graph_id"], "cli-graph")
            self.assertEqual(payload["edges"][0]["gene_id"], "GENE1")
            self.assertEqual(payload["degree_by_node"]["variant:v1"], 1)


if __name__ == "__main__":
    unittest.main()
