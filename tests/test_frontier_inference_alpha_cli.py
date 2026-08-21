from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierInferenceAlphaCliTests(unittest.TestCase):
    def test_federated_summary_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "federated.json"
            source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "records": [
                            {"feature_id": "f-1", "site_id": "site-a", "count": 10, "mean": 0.4},
                            {"feature_id": "f-1", "site_id": "site-b", "count": 12, "mean": 0.6},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.json"
            self.assertEqual(
                main(["analyze-federated-summary", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["supported_ids"], ["f-1"])

    def test_selective_prediction_command_can_abstain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "prediction.json"
            source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "records": [{"prediction_id": "p-1", "score": 0.4, "uncertainty": 0.3}],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.json"
            self.assertEqual(
                main(["selective-causal-prediction", str(source), "--output", str(output)]), 0
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["abstained_ids"], ["p-1"])


if __name__ == "__main__":
    unittest.main()
