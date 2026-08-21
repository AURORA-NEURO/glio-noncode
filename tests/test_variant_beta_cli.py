from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class VariantBetaCliTests(unittest.TestCase):
    def test_normalize_categorical_command_emits_catalog_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            catalog = root / "catalog.tsv"
            output = root / "result.json"
            raw.write_text(json.dumps({"id": "var-7"}), encoding="utf-8")
            catalog.write_text(
                "category_id\tlabel\tdefinition\tmembers\trules\n"
                'CAT-REG\tregulatory\tdeclared\tvar-7\t{"mode":"exact"}\n',
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "normalize-categorical",
                        str(raw),
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
            self.assertEqual(payload["catalog"]["definitions"][0]["category_id"], "CAT-REG")

    def test_build_annotation_command_emits_va_shaped_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "annotation.json"
            output = root / "annotation-output.json"
            source.write_text(
                json.dumps(
                    {
                        "annotation_id": "ann-1",
                        "subject": {"id": "vrs:1", "type": "Allele"},
                        "statements": [
                            {
                                "id": "s1",
                                "subject_id": "vrs:1",
                                "predicate": "effect",
                                "object": "active",
                                "object_type": "term",
                                "evidence_ids": ["e1"],
                                "summary": "declared effect",
                            }
                        ],
                        "evidence_lines": [
                            {
                                "id": "e1",
                                "source_id": "source:1",
                                "source_version": "v1",
                                "raw_hash": "a" * 64,
                                "summary": "source receipt",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "build-annotation",
                        str(source),
                        "--context-key",
                        "GRCh38|glioma|adult|unknown|unknown|unknown",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["va_spec_object"]["type"], "Statement")

    def test_decompose_multiallelic_command_emits_indexed_children(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "multi.json"
            output = root / "multi-output.json"
            source.write_text(
                json.dumps(
                    {
                        "variant_id": "parent",
                        "chrom": "7",
                        "pos": 100,
                        "ref": "A",
                        "alt": ["T", "C"],
                        "genotype": "1/2",
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "decompose-multiallelic",
                        str(source),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual([child["allele_index"] for child in payload["children"]], [1, 2])

    def test_normalize_repeat_command_uses_nested_variant_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "repeat.json"
            output = root / "repeat-output.json"
            source.write_text(
                json.dumps(
                    {
                        "variant": {
                            "variant_id": "ins",
                            "chrom": "1",
                            "pos": 102,
                            "ref": "A",
                            "alt": "AA",
                        },
                        "reference_sequence": "AAAAAA",
                        "reference_start": 100,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "normalize-repeat",
                        str(source),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "ambiguous")
            self.assertGreater(len(payload["placements"]), 1)
