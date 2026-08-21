from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierDataAlphaCliTests(unittest.TestCase):
    def test_frontier_commands_emit_json_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "frontier.json"
            source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "records": [
                            {
                                "record_id": "v-1",
                                "context_key": CONTEXT,
                                "consent_status": "granted",
                            }
                        ],
                        "policy_id": "policy-1",
                        "policy_version": "v1",
                        "purpose": "research",
                        "permitted_uses": ["nonclinical"],
                        "source_id": "consent-registry",
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.json"
            self.assertEqual(
                main(
                    [
                        "attach-consent-policy",
                        str(source),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["accepted_record_ids"], ["v-1"])
            self.assertTrue(payload["content_address"].startswith("sha256:"))

    def test_reference_release_gate_can_block_a_missing_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "release.json"
            source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "release_id": "release-1",
                        "bundle_address": "sha256:bundle",
                        "checks": {"checksum": True, "schema": False, "license": True},
                    }
                ),
                encoding="utf-8",
            )
            output = root / "output.json"
            self.assertEqual(
                main(["gate-reference-release", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "blocked")
            self.assertIn("schema", payload["failed_checks"])


if __name__ == "__main__":
    unittest.main()
