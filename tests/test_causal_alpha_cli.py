from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


class CausalAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_mediation_sensitivity_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "mediators.json",
                {
                    "evidence": [
                        {
                            "evidence_id": "e1",
                            "mediator_kind": "sequence_to_element",
                            "source_node": "variant:v1",
                            "target_node": "element:enh-1",
                            "context_key": CONTEXT,
                            "support": 0.8,
                            "uncertainty": 0.1,
                            "source_id": "seq",
                        },
                        {
                            "evidence_id": "e2",
                            "mediator_kind": "sequence_to_element",
                            "source_node": "variant:v1",
                            "target_node": "element:enh-1",
                            "context_key": CONTEXT,
                            "support": 0.7,
                            "uncertainty": 0.1,
                            "source_id": "motif",
                        },
                    ]
                },
            )
            output = root / "sensitivity.json"
            self.assertEqual(
                main(
                    [
                        "analyze-mediation-sensitivity",
                        str(source),
                        "--mediator-kind",
                        "sequence_to_element",
                        "--source-node",
                        "variant:v1",
                        "--target-node",
                        "element:enh-1",
                        "--context-key",
                        CONTEXT,
                        "--model-id",
                        "seq-alpha",
                        "--model-version",
                        "1",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["result"]["base_state"], "supported")
            self.assertEqual(len(payload["result"]["leave_one_out"]), 2)

    def test_confounding_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "confounders.json",
                {
                    "observations": [
                        {
                            "observation_id": "batch-1",
                            "confounder_id": "batch",
                            "label": "batch",
                            "status": "addressed",
                            "severity": 0.4,
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            output = root / "confounders-output.json"
            self.assertEqual(
                main(
                    [
                        "adjudicate-confounding",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--required-confounder",
                        "batch",
                        "--required-confounder",
                        "purity",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "partial")
            self.assertEqual(payload["missing_confounder_ids"], ["purity"])

    def test_dependence_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "dependence.json",
                {
                    "observations": [
                        {
                            "evidence_id": "e1",
                            "edge_id": "edge-1",
                            "method_family": "contact",
                            "dependence_group": "hic",
                            "support": 0.8,
                            "uncertainty": 0.1,
                            "context_key": CONTEXT,
                        },
                        {
                            "evidence_id": "e2",
                            "edge_id": "edge-1",
                            "method_family": "qtl",
                            "dependence_group": "qtl",
                            "support": 0.7,
                            "uncertainty": 0.1,
                            "context_key": CONTEXT,
                        },
                    ]
                },
            )
            output = root / "dependence-output.json"
            self.assertEqual(
                main(
                    [
                        "correct-evidence-dependence",
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
            self.assertEqual(payload["results"][0]["independent_group_count"], 2)

    def test_negative_evidence_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "negative.json",
                {
                    "observations": [
                        {
                            "evidence_id": "negative",
                            "edge_id": "edge-1",
                            "polarity": "negative_control",
                            "strength": 0.9,
                            "negative_control": True,
                            "context_key": CONTEXT,
                        }
                    ]
                },
            )
            output = root / "negative-output.json"
            self.assertEqual(
                main(
                    [
                        "integrate-negative-evidence",
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
            self.assertEqual(payload["state"], "measured_negative")
            self.assertEqual(payload["results"][0]["negative_control_ids"], ["negative"])


if __name__ == "__main__":
    unittest.main()
