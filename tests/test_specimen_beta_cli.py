from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class SpecimenBetaCliTests(unittest.TestCase):
    def _run(self, command: str, payload: object, *arguments: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            output = root / "output.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                main([command, str(source), *arguments, "--output", str(output)]),
                0,
            )
            return json.loads(output.read_text(encoding="utf-8"))

    def test_classify_origin_command(self) -> None:
        result = self._run(
            "classify-origin",
            {
                "records": [
                    {
                        "variant_id": "v1",
                        "relationship": "tumor",
                        "tumor_vaf": 0.4,
                        "present_in_normal": False,
                    }
                ]
            },
        )
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["classifications"][0]["origin"], "somatic")

    def test_estimate_mosaicism_command(self) -> None:
        result = self._run(
            "estimate-mosaicism",
            {
                "records": [
                    {"variant_id": "v1", "tissue_id": "skin", "vaf": 0.1},
                    {"variant_id": "v1", "tissue_id": "blood", "vaf": 0.08},
                ]
            },
        )
        self.assertEqual(result["state"], "supported")
        self.assertFalse(result["estimates"][0]["calibrated"])

    def test_estimate_ccf_command(self) -> None:
        result = self._run(
            "estimate-ccf",
            {
                "records": [
                    {
                        "variant_id": "v1",
                        "sample_id": "tumor-1",
                        "purity": 0.5,
                        "vaf": 0.25,
                        "total_copy_number": 2,
                        "alternate_copy_number": 1,
                    }
                ]
            },
        )
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["estimates"][0]["estimated_ccf"], 1.0)

    def test_assign_subclones_command(self) -> None:
        result = self._run(
            "assign-subclones",
            {
                "records": [
                    {"sample_id": "tumor-1", "variant_id": "v1", "ccf": 0.8},
                    {"sample_id": "tumor-1", "variant_id": "v2", "ccf": 0.75},
                ]
            },
        )
        self.assertEqual(result["state"], "supported")
        self.assertEqual(len(result["cluster_means"]), 1)
