from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


class CohortAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_clonality_timing_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "clonality.json",
                {
                    "observations": [
                        {
                            "observation_id": "c-1",
                            "variant_id": "v1",
                            "sample_id": "s1",
                            "cancer_cell_fraction": 0.9,
                            "phase": "primary",
                            "timepoint": 1,
                            "context_key": CONTEXT,
                        },
                        {
                            "observation_id": "c-2",
                            "variant_id": "v1",
                            "sample_id": "s2",
                            "cancer_cell_fraction": 0.88,
                            "phase": "recurrence",
                            "timepoint": 2,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "clonality-output.json"
            self.assertEqual(
                main(
                    [
                        "integrate-clonality-timing",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["clonality_label"], "clonal")

    def test_primary_recurrence_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "phases.json",
                {
                    "records": [
                        {
                            "observation_id": "p-1",
                            "variant_id": "v1",
                            "locus_id": "l1",
                            "sample_id": "p",
                            "phase": "primary",
                            "frequency": 0.2,
                            "context_key": CONTEXT,
                        },
                        {
                            "observation_id": "r-1",
                            "variant_id": "v1",
                            "locus_id": "l1",
                            "sample_id": "r",
                            "phase": "recurrence",
                            "frequency": 0.6,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "phases-output.json"
            self.assertEqual(
                main(
                    [
                        "compare-primary-recurrence",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["label"], "enriched")

    def test_treatment_selection_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "treatment.json",
                {
                    "observations": [
                        {
                            "observation_id": "pre",
                            "variant_id": "v1",
                            "sample_id": "pre-sample",
                            "treatment_id": "drug-a",
                            "selection_phase": "pre_treatment",
                            "frequency": 0.2,
                            "context_key": CONTEXT,
                        },
                        {
                            "observation_id": "post",
                            "variant_id": "v1",
                            "sample_id": "post-sample",
                            "treatment_id": "drug-a",
                            "selection_phase": "post_treatment",
                            "frequency": 0.6,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "treatment-output.json"
            self.assertEqual(
                main(
                    [
                        "detect-treatment-selection",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["selection_label"], "enriched")

    def test_cross_cohort_replication_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "replication.json",
                {
                    "observations": [
                        {
                            "observation_id": "a",
                            "feature_id": "v1",
                            "cohort_id": "a",
                            "effect": 0.4,
                            "support": 0.8,
                            "sample_count": 10,
                            "context_key": CONTEXT,
                        },
                        {
                            "observation_id": "b",
                            "feature_id": "v1",
                            "cohort_id": "b",
                            "effect": 0.3,
                            "support": 0.7,
                            "sample_count": 12,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "replication-output.json"
            self.assertEqual(
                main(
                    [
                        "replicate-cross-cohort",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertTrue(payload["results"][0]["replicated"])


if __name__ == "__main__":
    unittest.main()
