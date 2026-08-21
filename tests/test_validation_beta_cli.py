from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


def target() -> dict[str, object]:
    return {
        "target_id": "target-1",
        "variant_id": "v1",
        "element_id": "enh-1",
        "sequence": "A" * 20 + "C" + "A" * 20,
        "variant_offset": 20,
        "reference_allele": "C",
        "alternate_allele": "T",
        "context_key": CONTEXT,
        "source_id": "sequence-source",
        "source_version": "v1",
    }


class ValidationBetaCliTests(unittest.TestCase):
    def test_crispri_crispra_and_base_editing_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "targets.json"
            source.write_text(json.dumps({"targets": [target()]}), encoding="utf-8")
            for command, expected_mode in (
                ("plan-crispri", "crispri"),
                ("plan-crispra", "crispra"),
                ("plan-base-editing", "base_editing"),
            ):
                output = root / f"{command}.json"
                self.assertEqual(
                    main(
                        [
                            command,
                            str(source),
                            "--context-key",
                            CONTEXT,
                            "--max-guides",
                            "20",
                            "--output",
                            str(output),
                        ]
                    ),
                    0,
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(payload["mode"], expected_mode)
                self.assertEqual(payload["state"], "ready_for_review")
                self.assertTrue(payload["guides"])

    def test_prime_editing_and_allele_reporter_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "targets.json"
            source.write_text(json.dumps({"targets": [target()]}), encoding="utf-8")
            prime_output = root / "prime.json"
            self.assertEqual(
                main(
                    [
                        "plan-prime-editing",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--max-guides",
                        "20",
                        "--output",
                        str(prime_output),
                    ]
                ),
                0,
            )
            prime = json.loads(prime_output.read_text(encoding="utf-8"))
            self.assertEqual(prime["state"], "ready_for_review")
            self.assertTrue(prime["guides"][0]["pbs_sequence"])
            self.assertTrue(prime["guides"][0]["rtt_sequence"])

            reporter_output = root / "reporter.json"
            self.assertEqual(
                main(
                    [
                        "plan-allele-specific-reporter",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--max-guides",
                        "2",
                        "--output",
                        str(reporter_output),
                    ]
                ),
                0,
            )
            reporter = json.loads(reporter_output.read_text(encoding="utf-8"))
            self.assertEqual(reporter["state"], "ready_for_review")
            self.assertEqual(
                {item["allele"] for item in reporter["constructs"]},
                {"reference", "alternate"},
            )


if __name__ == "__main__":
    unittest.main()
