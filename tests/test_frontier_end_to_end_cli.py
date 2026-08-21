from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierEndToEndCliTests(unittest.TestCase):
    def test_validation_pipeline_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "pipeline.json"
            source.write_text(
                json.dumps(
                    {
                        "pipeline_id": "pipeline-1",
                        "context_key": CONTEXT,
                        "risk_records": [
                            {
                                "target_id": "guide-1",
                                "on_target_score": 0.9,
                                "off_targets": [{"score": 0.05}],
                            }
                        ],
                        "package": {
                            "context_key": CONTEXT,
                            "experiments": [{"experiment_id": "exp-1"}],
                            "controls": [{"control_id": "ctrl-1"}],
                            "protocols": [{"protocol_id": "p-1"}],
                            "outputs": ["readout"],
                        },
                        "required_controls": ["ctrl-1"],
                        "required_outputs": ["readout"],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.json"
            self.assertEqual(
                main(["run-validation-frontier-pipeline", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "accepted")
            self.assertEqual(
                payload["completed_stage_ids"],
                [
                    "off_target_risk",
                    "value_of_information",
                    "experiment_package",
                    "execution_readiness",
                    "claim_update",
                ],
            )


if __name__ == "__main__":
    unittest.main()
