from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class WorkspaceAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_board_and_launch_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            board_source = self._write(
                root,
                "board.json",
                {
                    "experiments": [
                        {
                            "experiment_id": "exp-1",
                            "target_id": "target-1",
                            "title": "Perturbation",
                            "assay_type": "crispr",
                            "status": "ready",
                            "context_key": CONTEXT,
                            "source_id": "planning",
                            "readout": "expression",
                        }
                    ]
                },
            )
            board_output = root / "board-output.json"
            self.assertEqual(
                main(
                    [
                        "build-validation-board",
                        str(board_source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(board_output),
                    ]
                ),
                0,
            )
            board = json.loads(board_output.read_text(encoding="utf-8"))
            self.assertEqual(board["state"], "ready_for_review")
            self.assertEqual(board["columns"][1]["card_ids"], ["exp-1"])

            launch_source = self._write(
                root,
                "launch.json",
                {
                    "requests": [
                        {
                            "request_id": "request-1",
                            "artifact_id": "notebook-1",
                            "runtime": "python",
                            "mode": "notebook",
                            "context_key": CONTEXT,
                            "entrypoint": "analysis.main",
                            "parameters": {"limit": 5},
                            "source_id": "notebook-catalog",
                        }
                    ]
                },
            )
            launch_output = root / "launch-output.json"
            self.assertEqual(
                main(
                    [
                        "plan-notebook-launch",
                        str(launch_source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(launch_output),
                    ]
                ),
                0,
            )
            launch = json.loads(launch_output.read_text(encoding="utf-8"))
            self.assertEqual(launch["state"], "ready_for_review")
            self.assertIn("--parameter-hash", launch["launches"][0]["invocation"])

    def test_share_and_collaboration_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_source = self._write(
                root,
                "snapshot.json",
                {"payload": {"workspace_id": "workspace-1", "records": ["claim-1"]}},
            )
            snapshot_output = root / "snapshot-output.json"
            self.assertEqual(
                main(
                    [
                        "publish-shareable-snapshot",
                        str(snapshot_source),
                        "--snapshot-id",
                        "snapshot-1",
                        "--context-key",
                        CONTEXT,
                        "--key-id",
                        "key-1",
                        "--signing-secret",
                        "test-secret",
                        "--output",
                        str(snapshot_output),
                    ]
                ),
                0,
            )
            verify_output = root / "verify-output.json"
            self.assertEqual(
                main(
                    [
                        "verify-shareable-snapshot",
                        str(snapshot_output),
                        "--signing-secret",
                        "test-secret",
                        "--output",
                        str(verify_output),
                    ]
                ),
                0,
            )
            verification = json.loads(verify_output.read_text(encoding="utf-8"))
            self.assertEqual(verification["state"], "verified")

            collaboration_source = self._write(
                root,
                "collaboration.json",
                {
                    "members": [
                        {
                            "member_id": "reviewer-1",
                            "display_label": "Reviewer",
                            "role": "reviewer",
                            "context_key": CONTEXT,
                            "source_id": "roster",
                        }
                    ],
                    "requests": [
                        {
                            "request_id": "request-1",
                            "member_id": "reviewer-1",
                            "action": "approve",
                            "target_id": "claim-1",
                            "context_key": CONTEXT,
                            "reason": "review",
                        }
                    ],
                },
            )
            collaboration_output = root / "collaboration-output.json"
            self.assertEqual(
                main(
                    [
                        "evaluate-collaboration-access",
                        str(collaboration_source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(collaboration_output),
                    ]
                ),
                0,
            )
            collaboration = json.loads(collaboration_output.read_text(encoding="utf-8"))
            self.assertEqual(collaboration["state"], "allowed")
            self.assertTrue(collaboration["decisions"][0]["allowed"])


if __name__ == "__main__":
    unittest.main()
