from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class ChromatinFrontierEvidenceCliTests(unittest.TestCase):
    def test_domain_07_commands_are_functional(self) -> None:
        json_commands = (
            "evaluate-chromatin-frontier-fixture",
            "audit-chromatin-frontier-data",
            "replay-chromatin-frontier",
            "chromatin-frontier-quality-gate",
            "evaluate-chromatin-frontier-scenarios",
            "chromatin-frontier-policy",
            "chromatin-frontier-contracts",
            "chromatin-frontier-schema",
            "chromatin-frontier-metrics",
            "build-chromatin-frontier-bundle",
            "chromatin-frontier-lineage",
            "chromatin-frontier-reconciliation",
            "chromatin-frontier-review-view",
            "chromatin-frontier-trace",
            "run-chromatin-frontier-pipeline",
            "build-chromatin-frontier-release",
        )
        text_commands = (
            "export-chromatin-frontier-receipts-csv",
            "export-chromatin-frontier-review-csv",
            "export-chromatin-frontier-review-markdown",
            "export-chromatin-frontier-metrics-csv",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, command in enumerate(json_commands):
                output = root / f"{index}-{command}.json"
                arguments = [command]
                if command == "run-chromatin-frontier-pipeline":
                    arguments.extend(("--run-id", "d07-cli", "--fail-on-review"))
                if command in {"chromatin-frontier-trace", "build-chromatin-frontier-release"}:
                    arguments.extend(("--run-id", f"d07-{index}"))
                arguments.extend(("--output", str(output)))
                self.assertEqual(main(arguments), 0, command)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)
                self.assertTrue(payload)
            for index, command in enumerate(text_commands):
                output = root / f"{index}-{command}.txt"
                self.assertEqual(main([command, "--output", str(output)]), 0, command)
                text = output.read_text(encoding="utf-8")
                self.assertTrue(text)
                self.assertNotIn("input_text", text)

    def test_domain_07_cli_accepts_the_checked_in_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.json"
            output = root / "evaluation.json"
            source.write_text(
                json.dumps(
                    __import__(
                        "glio_noncode.chromatin_frontier_public_data",
                        fromlist=["default_chromatin_frontier_fixture"],
                    )
                    .default_chromatin_frontier_fixture()
                    .to_dict()
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(["evaluate-chromatin-frontier-fixture", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(len(payload["receipts"]), 16)
            self.assertEqual(len(payload["checks"]), 120)


if __name__ == "__main__":
    unittest.main()
