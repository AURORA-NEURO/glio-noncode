from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class SequenceBetaCliTests(unittest.TestCase):
    def test_scan_motif_disruption_and_creation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "motifs.json"
            disruption_output = root / "disruption.json"
            creation_output = root / "creation.json"
            source.write_text(
                json.dumps(
                    {
                        "variant_id": "var-cli-1",
                        "reference_sequence": "TTTGATACCC",
                        "alternate_sequence": "TTTGGACCC",
                        "context_key": CONTEXT,
                        "motifs": [
                            {
                                "motif_id": "TF:GATA",
                                "name": "GATA factor",
                                "consensus": "GATA",
                                "source_id": "motif-catalog",
                                "source_version": "2026.1",
                                "strand_aware": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(["scan-motif-disruption", str(source), "--output", str(disruption_output)]),
                0,
            )
            disruption = json.loads(disruption_output.read_text(encoding="utf-8"))
            self.assertEqual(disruption["state"], "supported")
            self.assertEqual(disruption["context_key"], CONTEXT)
            self.assertEqual(disruption["disrupted_hits"][0]["motif_id"], "TF:GATA")

            source.write_text(
                json.dumps(
                    {
                        "variant_id": "var-cli-1",
                        "reference_sequence": "TTTGGACCC",
                        "alternate_sequence": "TTTGATACCC",
                        "motifs": [
                            {
                                "motif_id": "TF:GATA",
                                "name": "GATA factor",
                                "consensus": "GATA",
                                "source_id": "motif-catalog",
                                "source_version": "2026.1",
                                "strand_aware": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(["scan-motif-creation", str(source), "--output", str(creation_output)]),
                0,
            )
            creation = json.loads(creation_output.read_text(encoding="utf-8"))
            self.assertEqual(creation["created_hits"][0]["motif_id"], "TF:GATA")

    def test_grammar_analysis_and_cooperative_score_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            grammar_source = root / "grammar.json"
            grammar_output = root / "grammar-output.json"
            score_output = root / "score-output.json"
            payload = {
                "sequence_id": "window-cli-2",
                "sequence": "GATATTTACGT",
                "context_key": CONTEXT,
                "hits": [
                    {
                        "motif_id": "TF:GATA",
                        "motif_name": "GATA factor",
                        "start": 1,
                        "end": 4,
                        "strand": "+",
                        "matched_sequence": "GATA",
                        "score": 1.0,
                    },
                    {
                        "motif_id": "TF:ACGT",
                        "motif_name": "ACGT factor",
                        "start": 8,
                        "end": 11,
                        "strand": "+",
                        "matched_sequence": "ACGT",
                        "score": 1.0,
                    },
                ],
                "rules": [
                    {
                        "rule_id": "grammar-cli-1",
                        "motif_a": "TF:GATA",
                        "motif_b": "TF:ACGT",
                        "minimum_spacing": 3,
                        "maximum_spacing": 3,
                        "allowed_orientations": ["same"],
                    }
                ],
                "interactions": [
                    {
                        "interaction_id": "co-op-cli-1",
                        "motif_a": "TF:GATA",
                        "motif_b": "TF:ACGT",
                        "weight": 1.25,
                        "maximum_spacing": 3,
                        "required": True,
                        "source_version": "2026.1",
                    }
                ],
            }
            grammar_source.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "analyze-motif-grammar",
                        str(grammar_source),
                        "--output",
                        str(grammar_output),
                    ]
                ),
                0,
            )
            grammar = json.loads(grammar_output.read_text(encoding="utf-8"))
            self.assertEqual(grammar["state"], "supported")
            self.assertEqual(grammar["observations"][0]["spacing"], 3)

            self.assertEqual(
                main(
                    [
                        "score-cooperative-grammar",
                        str(grammar_source),
                        "--model-id",
                        "declared-grammar",
                        "--model-version",
                        "2026.1",
                        "--output",
                        str(score_output),
                    ]
                ),
                0,
            )
            score = json.loads(score_output.read_text(encoding="utf-8"))
            self.assertEqual(score["state"], "supported")
            self.assertEqual(score["score"], 1.25)
            self.assertIn("not a probability", " ".join(score["warnings"]))


if __name__ == "__main__":
    unittest.main()
