from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"


class CellContextAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_spatial_niche_prior_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "spatial.json",
                {
                    "records": [
                        {
                            "subject_id": "case-1",
                            "niche_id": "vascular",
                            "support": 0.8,
                            "context_key": CONTEXT,
                        },
                        {
                            "subject_id": "case-1",
                            "niche_id": "vascular",
                            "support": 0.75,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["estimate-spatial-niche-prior", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["niche_id"], "vascular")

    def test_core_margin_prior_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "core-margin.json",
                {"records": [{"subject_id": "case-1", "core_score": 0.8, "margin_score": 0.2}]},
            )
            output = root / "out.json"
            self.assertEqual(
                main(["estimate-core-margin-prior", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["territory_label"], "core")

    def test_recurrence_state_prior_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "recurrence.json",
                {
                    "records": [
                        {"subject_id": "case-1", "phase": "primary", "support": 0.8},
                        {"subject_id": "case-1", "phase": "primary", "support": 0.82},
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["estimate-recurrence-state-prior", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["phase"], "primary")

    def test_treatment_induced_state_prior_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "treatment.json",
                {
                    "records": [
                        {
                            "subject_id": "case-1",
                            "treatment_id": "tmz",
                            "state_id": "mesenchymal",
                            "baseline_support": 0.2,
                            "post_treatment_support": 0.75,
                            "treatment_phase": "post_treatment",
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    ["estimate-treatment-induced-state-prior", str(source), "--output", str(output)]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["induction_label"], "induced")


if __name__ == "__main__":
    unittest.main()
