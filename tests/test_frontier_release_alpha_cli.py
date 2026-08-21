from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierReleaseAlphaCliTests(unittest.TestCase):
    def test_off_target_and_rollback_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            risk_source = root / "risk.json"
            risk_source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "records": [
                            {
                                "target_id": "guide-1",
                                "on_target_score": 0.9,
                                "off_targets": [{"score": 0.05}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            risk_output = root / "risk-output.json"
            self.assertEqual(
                main(["estimate-off-target-risk", str(risk_source), "--output", str(risk_output)]),
                0,
            )
            self.assertEqual(
                json.loads(risk_output.read_text(encoding="utf-8"))["low_risk_ids"], ["guide-1"]
            )
            release_source = root / "release.json"
            release_source.write_text(
                json.dumps(
                    {
                        "release_id": "rel-1",
                        "current_version": "1.0",
                        "requested_version": "0.9",
                        "action": "rollback",
                        "previous_version": "0.9",
                        "checks": {
                            "tests": True,
                            "integrity": True,
                            "compatibility": True,
                            "policy": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            release_output = root / "release-output.json"
            self.assertEqual(
                main(
                    [
                        "decide-release-rollback",
                        str(release_source),
                        "--output",
                        str(release_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(release_output.read_text(encoding="utf-8"))["state"], "rolled_back"
            )

    def test_signed_dossier_publish_and_verify_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "dossier.json"
            source.write_text(
                json.dumps(
                    {
                        "context_key": CONTEXT,
                        "dossier_id": "dossier-1",
                        "key_id": "key-1",
                        "signing_secret": "secret",
                        "audience": ["reviewer"],
                        "payload": {"claim_id": "claim-1"},
                    }
                ),
                encoding="utf-8",
            )
            signed = root / "signed.json"
            self.assertEqual(
                main(["publish-signed-dossier", str(source), "--output", str(signed)]), 0
            )
            verify_source = root / "verify.json"
            verify_source.write_text(
                json.dumps(
                    {
                        "dossier": json.loads(signed.read_text(encoding="utf-8")),
                        "signing_secret": "secret",
                        "audience": "reviewer",
                    }
                ),
                encoding="utf-8",
            )
            verified = root / "verified.json"
            self.assertEqual(
                main(["verify-signed-dossier", str(verify_source), "--output", str(verified)]), 0
            )
            self.assertEqual(json.loads(verified.read_text(encoding="utf-8"))["state"], "ready")


if __name__ == "__main__":
    unittest.main()
