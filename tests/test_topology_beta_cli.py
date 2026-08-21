from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


class TopologyBetaCliTests(unittest.TestCase):
    def test_loop_and_promoter_capture_parser_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loop_source = root / "loops.tsv"
            loop_output = root / "loops.json"
            loop_source.write_text(
                "feature_id\tfeature_kind\tchrom1\tstart1\tend1\tchrom2\tstart2\tend2\tsignal\tcontext\n"
                f"loop-1\tloop\t7\t99\t120\t7\t299\t320\t12\t{CONTEXT}\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-loop-stripe", str(loop_source), "--output", str(loop_output)]),
                0,
            )
            loops = json.loads(loop_output.read_text(encoding="utf-8"))
            self.assertEqual(loops["observations"][0]["feature_kind"], "loop")

            promoter_source = root / "promoter.json"
            promoter_output = root / "promoter-output.json"
            promoter_source.write_text(
                json.dumps(
                    {
                        "contacts": [
                            {
                                "contact_id": "pc-1",
                                "promoter_id": "GENE1",
                                "target_element_id": "enh-1",
                                "promoter_chromosome": "7",
                                "promoter_start": 100,
                                "promoter_end": 120,
                                "target_chromosome": "7",
                                "target_start": 300,
                                "target_end": 320,
                                "signal": 5,
                                "context_key": CONTEXT,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-promoter-capture",
                        str(promoter_source),
                        "--coordinate-system",
                        "one_based",
                        "--output",
                        str(promoter_output),
                    ]
                ),
                0,
            )
            promoter = json.loads(promoter_output.read_text(encoding="utf-8"))
            self.assertEqual(promoter["contacts"][0]["target_element_id"], "enh-1")

    def test_contact_and_activity_by_contact_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "scores.json"
            contact_output = root / "contact-output.json"
            abc_output = root / "abc-output.json"
            source.write_text(
                json.dumps(
                    {
                        "contacts": [
                            {
                                "contact_id": "pc-1",
                                "enhancer_id": "enh-1",
                                "promoter_id": "GENE1",
                                "signal": 5,
                                "context_key": CONTEXT,
                                "source_id": "pc-atlas",
                                "source_version": "v1",
                            }
                        ],
                        "activities": [
                            {
                                "enhancer_id": "enh-1",
                                "activity_signal": 0.8,
                                "context_key": CONTEXT,
                                "source_id": "activity-atlas",
                                "source_version": "v2",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "score-enhancer-promoter-contact",
                        str(source),
                        "--enhancer-id",
                        "enh-1",
                        "--promoter-id",
                        "GENE1",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(contact_output),
                    ]
                ),
                0,
            )
            contact = json.loads(contact_output.read_text(encoding="utf-8"))
            self.assertEqual(contact["state"], "supported")
            self.assertEqual(contact["normalized_contact_score"], 0.5)

            self.assertEqual(
                main(
                    [
                        "score-activity-by-contact",
                        str(source),
                        "--enhancer-id",
                        "enh-1",
                        "--promoter-id",
                        "GENE1",
                        "--context-key",
                        CONTEXT,
                        "--model-id",
                        "abc-model",
                        "--model-version",
                        "v1",
                        "--output",
                        str(abc_output),
                    ]
                ),
                0,
            )
            abc = json.loads(abc_output.read_text(encoding="utf-8"))
            self.assertEqual(abc["state"], "supported")
            self.assertEqual(abc["activity_by_contact_score"], 0.4)


if __name__ == "__main__":
    unittest.main()
