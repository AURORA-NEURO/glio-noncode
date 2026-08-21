from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class PlatformAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_execution_ledger_and_monitor_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger_source = self._write(
                root,
                "events.json",
                {
                    "events": [
                        {"event_id": "e-1", "kind": "requested", "message": "requested"},
                        {"event_id": "e-2", "kind": "planned", "message": "planned"},
                        {"event_id": "e-3", "kind": "admitted", "message": "admitted"},
                        {"event_id": "e-4", "kind": "started", "message": "started"},
                        {"event_id": "e-5", "kind": "completed", "message": "completed"},
                    ]
                },
            )
            ledger_output = root / "ledger-output.json"
            self.assertEqual(
                main(
                    [
                        "replay-execution-ledger",
                        str(ledger_source),
                        "--execution-id",
                        "execution-1",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(ledger_output),
                    ]
                ),
                0,
            )
            ledger = json.loads(ledger_output.read_text(encoding="utf-8"))
            self.assertEqual(ledger["state"], "completed")
            self.assertEqual(ledger["last_sequence"], 5)

            monitor_source = self._write(
                root,
                "monitor.json",
                {
                    "observations": [
                        {
                            "observation_id": "obs-1",
                            "monitor_id": "monitor-1",
                            "feature_id": "feature-1",
                            "context_key": CONTEXT,
                            "metric": "mean_delta",
                            "reference_value": 0.1,
                            "current_value": 0.6,
                            "watch_threshold": 0.1,
                            "drift_threshold": 0.3,
                            "source_id": "monitor-source",
                        }
                    ]
                },
            )
            monitor_output = root / "monitor-output.json"
            self.assertEqual(
                main(
                    [
                        "monitor-drift",
                        str(monitor_source),
                        "--monitor-id",
                        "monitor-1",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(monitor_output),
                    ]
                ),
                0,
            )
            monitor = json.loads(monitor_output.read_text(encoding="utf-8"))
            self.assertEqual(monitor["state"], "drift")

    def test_model_and_data_registry_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_source = self._write(
                root,
                "models.json",
                {
                    "records": [
                        {
                            "model_id": "model-1",
                            "version": "v1",
                            "model_family": "sequence",
                            "artifact_digest": "sha256:model",
                            "input_contract": "sequence-window",
                            "output_contract": "effect-envelope",
                            "supported_contexts": [CONTEXT],
                            "status": "validated",
                            "source_id": "model-source",
                            "license_id": "research",
                            "evaluation_receipt": "sha256:evaluation",
                        }
                    ]
                },
            )
            model_output = root / "model-output.json"
            self.assertEqual(
                main(
                    [
                        "resolve-model-registry",
                        str(model_source),
                        "--model-id",
                        "model-1",
                        "--context-key",
                        CONTEXT,
                        "--input-contract",
                        "sequence-window",
                        "--output",
                        str(model_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(model_output.read_text(encoding="utf-8"))["state"],
                "compatible",
            )
            data_source = self._write(
                root,
                "data.json",
                {
                    "records": [
                        {
                            "dataset_id": "reference-1",
                            "version": "v1",
                            "reference_kind": "genome",
                            "source_uri": "https://example.test/reference",
                            "checksum": "sha256:reference",
                            "format": "fasta",
                            "schema_hash": "sha256:schema",
                            "supported_contexts": [CONTEXT],
                            "coordinate_system": "GRCh38",
                            "license_id": "research",
                            "status": "available",
                            "source_id": "data-source",
                            "retrieval_receipt": "sha256:retrieval",
                        }
                    ]
                },
            )
            data_output = root / "data-output.json"
            self.assertEqual(
                main(
                    [
                        "resolve-data-reference",
                        str(data_source),
                        "--dataset-id",
                        "reference-1",
                        "--context-key",
                        CONTEXT,
                        "--coordinate-system",
                        "GRCh38",
                        "--output",
                        str(data_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(data_output.read_text(encoding="utf-8"))["state"],
                "compatible",
            )


if __name__ == "__main__":
    unittest.main()
