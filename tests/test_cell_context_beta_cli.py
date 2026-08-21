from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
GBM_CONTEXT = "GRCh38|glioblastoma|adult|stem_like|core|unknown"
IDH_CONTEXT = "GRCh38|glioma|adult|proneural|core|unknown"
H3_CONTEXT = "GRCh38|glioma|pediatric|stem_like|midline|unknown"


def observation(observation_id: str, candidate_id: str, context_key: str) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "subject_id": "case-cli",
        "candidate_id": candidate_id,
        "candidate_label": candidate_id.replace("_", " "),
        "context_key": context_key,
        "support": 0.9,
        "uncertainty": 0.1,
        "source_id": "prior-atlas",
        "source_version": "v1",
        "evidence_tier": "reference-atlas",
    }


class CellContextBetaCliTests(unittest.TestCase):
    def test_parse_context_prior_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "prior.tsv"
            output = root / "prior.json"
            source.write_text(
                "observation_id\tcandidate_id\tcandidate_label\tcontext_key\tsupport\tuncertainty\n"
                f"obs-1\tradial_glia_like\tradial glia-like\t{CONTEXT}\t0.9\t0.1\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(["parse-context-prior", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["observations"][0]["candidate_id"], "radial_glia_like")

    def test_all_four_prior_command_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = (
                (
                    "estimate-developmental-lineage-prior",
                    CONTEXT,
                    "radial_glia_like",
                    (),
                    "supported",
                ),
                (
                    "estimate-glioblastoma-state-prior",
                    GBM_CONTEXT,
                    "stem_like",
                    (),
                    "supported",
                ),
                (
                    "estimate-idh-lineage-prior",
                    IDH_CONTEXT,
                    "proneural",
                    ("--molecular-state", "IDH-mutant"),
                    "supported",
                ),
                (
                    "estimate-h3k27-developmental-prior",
                    H3_CONTEXT,
                    "midline_glial_progenitor",
                    ("--molecular-state", "H3K27-altered"),
                    "supported",
                ),
            )
            for index, (command, context_key, candidate_id, extra, expected_state) in enumerate(
                cases
            ):
                source = root / f"prior-{index}.json"
                output = root / f"prior-{index}-output.json"
                source.write_text(
                    json.dumps(
                        {
                            "subject_id": "case-cli",
                            "observations": [
                                observation(f"obs-{index}", candidate_id, context_key)
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                args = [
                    command,
                    str(source),
                    "--context-key",
                    context_key,
                    "--subject-id",
                    "case-cli",
                    "--model-version",
                    "v1",
                    "--output",
                    str(output),
                    *extra,
                ]
                self.assertEqual(main(args), 0)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(payload["state"], expected_state)
                self.assertEqual(payload["selected_candidate_id"], candidate_id)


if __name__ == "__main__":
    unittest.main()
