from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


def recurrence(record_id: str, variant_id: str, sample_id: str, position: int) -> dict[str, object]:
    return {
        "record_id": record_id,
        "variant_id": variant_id,
        "sample_id": sample_id,
        "chromosome": "chr7",
        "position": position,
        "context_key": CONTEXT,
        "source_id": "cohort",
        "source_version": "v1",
        "region_id": "reg-1",
    }


class CohortBetaCliTests(unittest.TestCase):
    def test_recurrence_and_regional_burden_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recurrence_source = root / "recurrence.json"
            recurrence_parsed = root / "recurrence-parsed.json"
            recurrence_result = root / "recurrence-result.json"
            recurrence_source.write_text(
                json.dumps(
                    {
                        "records": [
                            recurrence("r1", "v1", "s1", 100),
                            recurrence("r2", "v1", "s2", 100),
                            recurrence("r3", "v2", "s2", 110),
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-regulatory-recurrence",
                        str(recurrence_source),
                        "--output",
                        str(recurrence_parsed),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "test-regulatory-recurrence",
                        str(recurrence_parsed),
                        "--context-key",
                        CONTEXT,
                        "--hotspot-window-bp",
                        "20",
                        "--output",
                        str(recurrence_result),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(recurrence_result.read_text(encoding="utf-8"))["state"],
                "supported",
            )

            regional_source = root / "regional.json"
            regional_parsed = root / "regional-parsed.json"
            regional_result = root / "regional-result.json"
            regional_source.write_text(
                json.dumps(
                    {
                        "regions": [
                            {
                                "region_id": "reg-1",
                                "chromosome": "chr7",
                                "start": 90,
                                "end": 200,
                                "callable_bases": 1000,
                                "context_key": CONTEXT,
                            }
                        ],
                        "observations": [
                            recurrence("r1", "v1", "s1", 100),
                            recurrence("r2", "v2", "s2", 120),
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-regional-burden",
                        str(regional_source),
                        "--output",
                        str(regional_parsed),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "test-regional-burden",
                        str(regional_parsed),
                        "--region-id",
                        "reg-1",
                        "--context-key",
                        CONTEXT,
                        "--background-rate",
                        "0.001",
                        "--output",
                        str(regional_result),
                    ]
                ),
                0,
            )
            regional = json.loads(regional_result.read_text(encoding="utf-8"))
            self.assertEqual(regional["state"], "supported")
            self.assertEqual(regional["observed_variant_count"], 2)

    def test_functional_and_pathway_convergence_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            functional_source = root / "functional.json"
            functional_parsed = root / "functional-parsed.json"
            functional_result = root / "functional-result.json"
            functional_source.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "observation_id": "f1",
                                "variant_id": "v1",
                                "sample_id": "s1",
                                "feature_id": "motif-loss",
                                "feature_class": "sequence",
                                "support": 0.9,
                                "direction": "loss",
                                "context_key": CONTEXT,
                            },
                            {
                                "observation_id": "f2",
                                "variant_id": "v2",
                                "sample_id": "s2",
                                "feature_id": "motif-loss",
                                "feature_class": "sequence",
                                "support": 0.8,
                                "direction": "loss",
                                "context_key": CONTEXT,
                            },
                            {
                                "observation_id": "c1",
                                "variant_id": "c1",
                                "sample_id": "cs1",
                                "feature_id": "motif-loss",
                                "feature_class": "sequence",
                                "support": 0.2,
                                "direction": "loss",
                                "context_key": CONTEXT,
                                "is_control": True,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-functional-convergence",
                        str(functional_source),
                        "--output",
                        str(functional_parsed),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "test-functional-convergence",
                        str(functional_parsed),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(functional_result),
                    ]
                ),
                0,
            )
            functional = json.loads(functional_result.read_text(encoding="utf-8"))
            self.assertEqual(functional["state"], "supported")
            self.assertEqual(functional["leading_feature_ids"], ["motif-loss"])

            pathway_source = root / "pathway.json"
            pathway_parsed = root / "pathway-parsed.json"
            pathway_result = root / "pathway-result.json"
            common = {
                "set_id": "path-a",
                "set_kind": "pathway",
                "support": 0.8,
                "direction": "activated",
                "context_key": CONTEXT,
            }
            pathway_source.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                **common,
                                "observation_id": "p1",
                                "variant_id": "v1",
                                "sample_id": "s1",
                                "gene_id": "GENE1",
                            },
                            {
                                **common,
                                "observation_id": "p2",
                                "variant_id": "v2",
                                "sample_id": "s2",
                                "gene_id": "GENE2",
                                "support": 0.7,
                            },
                            {
                                **common,
                                "observation_id": "c1",
                                "variant_id": "c1",
                                "sample_id": "cs1",
                                "gene_id": "GENE1",
                                "support": 0.2,
                                "is_control": True,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-pathway-regulon",
                        str(pathway_source),
                        "--output",
                        str(pathway_parsed),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "test-pathway-regulon-convergence",
                        str(pathway_parsed),
                        "--context-key",
                        CONTEXT,
                        "--set-kind",
                        "pathway",
                        "--output",
                        str(pathway_result),
                    ]
                ),
                0,
            )
            pathway = json.loads(pathway_result.read_text(encoding="utf-8"))
            self.assertEqual(pathway["state"], "supported")
            self.assertEqual(pathway["leading_set_ids"], ["path-a"])


if __name__ == "__main__":
    unittest.main()
