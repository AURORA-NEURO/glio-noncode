from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class SpecimenLineageCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_multi_region_lineage_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "regions.json",
                {
                    "records": [
                        {
                            "region_id": "r1",
                            "sample_id": "s1",
                            "subject_id": "u1",
                            "region_label": "primary",
                            "relationship": "root",
                        },
                        {
                            "region_id": "r2",
                            "sample_id": "s2",
                            "subject_id": "u1",
                            "region_label": "region-2",
                            "parent_region_id": "r1",
                            "relationship": "derived",
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["resolve-multi-region-lineage", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "supported")
            self.assertEqual(payload["lineages"][0]["roots"], ["r1"])

    def test_longitudinal_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "specimens.json",
                {
                    "records": [
                        {
                            "specimen_id": "s1",
                            "sample_id": "a",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-01-01",
                        },
                        {
                            "specimen_id": "s2",
                            "sample_id": "b",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-02-01",
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["link-longitudinal-specimens", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["links"][0]["ordering_basis"], "ordered_time")

    def test_primary_recurrence_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "phases.json",
                {
                    "records": [
                        {
                            "specimen_id": "s1",
                            "sample_id": "a",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-01-01",
                            "phase": "primary",
                        },
                        {
                            "specimen_id": "s2",
                            "sample_id": "b",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-02-01",
                            "phase": "recurrence",
                        },
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(["map-primary-recurrence", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                [item["phase"] for item in payload["assignments"]], ["primary", "recurrence"]
            )

    def test_treatment_context_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "specimens.json",
                {
                    "records": [
                        {
                            "specimen_id": "s1",
                            "sample_id": "a",
                            "subject_id": "u1",
                            "tissue": "tumor",
                            "collection_time": "2024-02-01",
                        }
                    ]
                },
            )
            exposures = self._write(
                root,
                "exposures.json",
                {
                    "exposures": [
                        {
                            "exposure_id": "e1",
                            "subject_id": "u1",
                            "therapy_id": "drug-a",
                            "start_time": "2024-01-01",
                            "end_time": "2024-03-01",
                        }
                    ]
                },
            )
            output = root / "out.json"
            self.assertEqual(
                main(
                    [
                        "contextualize-treatment",
                        str(source),
                        "--exposures",
                        str(exposures),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["contexts"][0]["relation"], "on_treatment")


if __name__ == "__main__":
    unittest.main()
