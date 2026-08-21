from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class FrontierReleaseHardeningCliTests(unittest.TestCase):
    def test_render_artifact_and_security_scan_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_source = root / "artifact.json"
            artifact_source.write_text(
                json.dumps(
                    {
                        "artifact_id": "report.csv",
                        "format": "csv",
                        "columns": ["id", "state"],
                        "rows": [{"id": "claim-1", "state": "review"}],
                    }
                ),
                encoding="utf-8",
            )
            artifact_output = root / "artifact-output.json"
            self.assertEqual(
                main(
                    [
                        "render-report-artifact",
                        str(artifact_source),
                        "--output",
                        str(artifact_output),
                    ]
                ),
                0,
            )
            artifact = json.loads(artifact_output.read_text(encoding="utf-8"))
            self.assertIn("id,state", artifact["content"])
            security_source = root / "security.json"
            security_source.write_text(
                json.dumps({"payload": {"subject_id": "subject-1", "token": "secret"}}),
                encoding="utf-8",
            )
            security_output = root / "security-output.json"
            self.assertEqual(
                main(
                    ["scan-security-paths", str(security_source), "--output", str(security_output)]
                ),
                0,
            )
            security = json.loads(security_output.read_text(encoding="utf-8"))
            self.assertEqual(security["secret_path_count"], 1)
            self.assertNotIn("secret", security["findings"][0])

    def test_graph_and_privacy_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_source = root / "graph.json"
            graph_source.write_text(
                json.dumps(
                    {
                        "context_key": "GRCh38|glioma|adult|stem_like|core|untreated",
                        "nodes": [{"node_id": "a"}],
                        "edges": [{"source_id": "a", "target_id": "missing"}],
                    }
                ),
                encoding="utf-8",
            )
            graph_output = root / "graph-output.json"
            self.assertEqual(
                main(
                    [
                        "audit-evidence-graph-integrity",
                        str(graph_source),
                        "--output",
                        str(graph_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(graph_output.read_text(encoding="utf-8"))["dangling_node_ids"],
                ["missing"],
            )
            privacy_source = root / "privacy.json"
            privacy_source.write_text(
                json.dumps(
                    {
                        "epsilon_budget": 1.0,
                        "delta_budget": 0.1,
                        "requests": [
                            {
                                "request_id": "r-1",
                                "site_id": "site-a",
                                "epsilon": 0.4,
                                "delta": 0.01,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            privacy_output = root / "privacy-output.json"
            self.assertEqual(
                main(
                    [
                        "account-federated-privacy",
                        str(privacy_source),
                        "--output",
                        str(privacy_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(privacy_output.read_text(encoding="utf-8"))["allowed_ids"], ["r-1"]
            )


if __name__ == "__main__":
    unittest.main()
