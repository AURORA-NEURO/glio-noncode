from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class StructuralBetaCliTests(unittest.TestCase):
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

    def test_map_focal_amplification_command(self) -> None:
        payload = {
            "records": [
                {
                    "segment_id": "s1",
                    "caller_id": "caller-a",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "copy_number": 8,
                    "context_key": CONTEXT,
                },
                {
                    "segment_id": "s2",
                    "caller_id": "caller-b",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "copy_number": 7,
                    "context_key": CONTEXT,
                },
            ]
        }
        result = self._run("map-focal-amplification", payload, "--context-key", CONTEXT)
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["start"], 100)

    def test_detect_chromothripsis_command(self) -> None:
        payload = {
            "records": [
                {
                    "event_id": f"sv-{index}",
                    "chrom": "7",
                    "pos": 1000 + index * 100,
                    "orientation": "forward" if index % 2 == 0 else "reverse",
                    "copy_number_state": "high" if index % 2 == 0 else "low",
                }
                for index in range(6)
            ]
        }
        result = self._run(
            "detect-chromothripsis",
            payload,
            "--min-orientation-switches",
            "3",
        )
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["breakpoint_count"], 6)

    def test_detect_ecdna_command(self) -> None:
        payload = {
            "records": [
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-a",
                    "is_circular": True,
                    "junction_count": 3,
                    "copy_number": 12,
                },
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-b",
                    "is_circular": True,
                    "junction_count": 3,
                    "copy_number": 11,
                },
            ]
        }
        result = self._run("detect-ecdna", payload)
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["component_id"], "cycle-1")

    def test_detect_enhancer_hijacking_command(self) -> None:
        payload = {
            "records": [
                {
                    "event_id": "sv-1",
                    "enhancer_id": "enh-1",
                    "target_gene_id": "gene-a",
                    "context_key": CONTEXT,
                    "breakpoint_supported": True,
                    "activity_supported": True,
                }
            ]
        }
        result = self._run(
            "detect-enhancer-hijacking",
            payload,
            "--context-key",
            CONTEXT,
            "--minimum-evidence-channels",
            "2",
        )
        self.assertEqual(result["state"], "supported")
        self.assertEqual(result["candidates"][0]["target_gene_id"], "gene-a")
