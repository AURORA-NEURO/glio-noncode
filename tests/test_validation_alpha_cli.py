from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


class ValidationAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_model_system_eligibility_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "eligibility.json",
                {
                    "observations": [
                        {
                            "observation_id": "elig-1",
                            "target_id": "target-1",
                            "model_system": "organoid",
                            "context_key": CONTEXT,
                            "supported_contexts": [CONTEXT],
                            "cell_state": "stem_like",
                            "evidence_strength": 0.9,
                            "eligible": True,
                            "source_id": "model-source",
                        }
                    ]
                },
            )
            output = root / "eligibility-output.json"
            self.assertEqual(
                main(
                    [
                        "match-model-system-eligibility",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--model-system",
                        "organoid",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["results"][0]["state"], "eligible")

    def test_guide_oligo_parse_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "guides.json",
                {
                    "observations": [
                        {
                            "observation_id": "guide-1",
                            "design_id": "design-1",
                            "target_id": "target-1",
                            "oligo_id": "oligo-1",
                            "oligo_type": "guide",
                            "sequence": "ACGTN",
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            output = root / "guides-output.json"
            self.assertEqual(
                main(
                    [
                        "parse-guide-oligo-design",
                        str(source),
                        "--source-id",
                        "guide-source",
                        "--format",
                        "json",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["observations"]), 1)
            self.assertEqual(payload["observations"][0]["sequence"], "ACGTN")

    def test_controls_randomization_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "targets.json",
                {
                    "targets": [
                        {
                            "target_id": "target-1",
                            "context_key": CONTEXT,
                            "condition": "reporter",
                        }
                    ]
                },
            )
            output = root / "controls-output.json"
            self.assertEqual(
                main(
                    [
                        "plan-controls-randomization",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--biological-replicates",
                        "2",
                        "--technical-replicates",
                        "2",
                        "--control-type",
                        "negative",
                        "--control-type",
                        "non_targeting",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["assignments"]), 8)
            self.assertEqual(payload["state"], "ready_for_review")

    def test_power_replication_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "power.json",
                {
                    "observations": [
                        {
                            "observation_id": "power-1",
                            "design_id": "design-1",
                            "assay_id": "assay-1",
                            "effect_size": 0.5,
                            "variance": 0.25,
                            "planned_replicates": 50,
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            output = root / "power-output.json"
            self.assertEqual(
                main(
                    [
                        "estimate-power-replication",
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
            self.assertGreater(payload["results"][0]["required_replicates"], 0)


if __name__ == "__main__":
    unittest.main()
