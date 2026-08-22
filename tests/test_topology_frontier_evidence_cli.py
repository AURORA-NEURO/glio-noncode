from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class TopologyFrontierEvidenceCliTests(unittest.TestCase):
    def test_json_commands_write_valid_output(self) -> None:
        commands = (
            "audit-topology-frontier-data",
            "evaluate-topology-frontier-fixture",
            "replay-topology-frontier",
            "topology-frontier-quality-gate",
            "evaluate-topology-frontier-scenarios",
            "topology-frontier-policy",
            "topology-frontier-contracts",
            "topology-frontier-schema",
            "topology-frontier-metrics",
            "build-topology-frontier-bundle",
            "topology-frontier-lineage",
            "topology-frontier-reconciliation",
            "run-topology-frontier-pipeline",
            "build-topology-frontier-release",
            "topology-frontier-review-view",
            "topology-frontier-trace",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in commands:
                output = root / f"{command}.json"
                arguments = [command, "--output", str(output)]
                if command in {"run-topology-frontier-pipeline", "build-topology-frontier-release", "topology-frontier-trace"}:
                    arguments.extend(("--run-id", "d09-cli"))
                self.assertEqual(main(arguments), 0, command)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)

    def test_json_commands_accept_an_exported_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.json"
            output = root / "evaluation.json"
            from glio_noncode.topology_frontier_public_data import default_topology_frontier_fixture

            fixture.write_text(json.dumps(default_topology_frontier_fixture().to_dict()), encoding="utf-8")
            self.assertEqual(main(["evaluate-topology-frontier-fixture", str(fixture), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(len(payload["receipts"]), 16)

    def test_text_exports_have_expected_headers(self) -> None:
        commands = (
            ("export-topology-frontier-receipts-csv", "record_id,operation"),
            ("export-topology-frontier-review-csv", "record_id,operation"),
            ("export-topology-frontier-review-markdown", "# Topology frontier review"),
            ("export-topology-frontier-metrics-csv", "operation,record_count"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command, expected in commands:
                output = root / f"{command}.txt"
                self.assertEqual(main([command, "--output", str(output)]), 0, command)
                self.assertIn(expected, output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
