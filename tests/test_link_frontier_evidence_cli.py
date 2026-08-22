from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class LinkFrontierEvidenceCliTests(unittest.TestCase):
    def test_json_commands_write_valid_output(self) -> None:
        commands = (
            "audit-link-frontier-data",
            "evaluate-link-frontier-fixture",
            "replay-link-frontier",
            "link-frontier-quality-gate",
            "link-frontier-depth-audit",
            "evaluate-link-frontier-scenarios",
            "link-frontier-policy",
            "link-frontier-contracts",
            "link-frontier-schema",
            "link-frontier-metrics",
            "build-link-frontier-bundle",
            "link-frontier-lineage",
            "link-frontier-reconciliation",
            "run-link-frontier-pipeline",
            "build-link-frontier-release",
            "link-frontier-review-view",
            "link-frontier-trace",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in commands:
                output = root / f"{command}.json"
                arguments = [command, "--output", str(output)]
                if command in {"run-link-frontier-pipeline", "build-link-frontier-release", "link-frontier-trace"}:
                    arguments.extend(("--run-id", "d10-cli"))
                self.assertEqual(main(arguments), 0, command)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)

    def test_json_commands_accept_an_exported_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.json"
            output = root / "evaluation.json"
            from glio_noncode.link_frontier_public_data import default_link_frontier_fixture

            fixture.write_text(json.dumps(default_link_frontier_fixture().to_dict()), encoding="utf-8")
            self.assertEqual(main(["evaluate-link-frontier-fixture", str(fixture), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(len(payload["executions"]), 16)

    def test_text_exports_have_expected_headers(self) -> None:
        commands = (
            ("export-link-frontier-receipts-csv", "record_id,operation"),
            ("export-link-frontier-review-csv", "record_id,operation"),
            ("export-link-frontier-review-markdown", "# Link frontier review"),
            ("export-link-frontier-metrics-csv", "fixture_id,record_count"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command, expected in commands:
                output = root / f"{command}.txt"
                self.assertEqual(main([command, "--output", str(output)]), 0, command)
                self.assertIn(expected, output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
