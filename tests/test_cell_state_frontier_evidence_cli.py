from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cell_state_frontier_public_data import default_cell_state_frontier_fixture
from glio_noncode.cli import main


class CellStateFrontierEvidenceCliTests(unittest.TestCase):
    def test_domain_08_commands_are_functional(self) -> None:
        json_commands = (
            "evaluate-cell-state-frontier-fixture",
            "audit-cell-state-frontier-data",
            "replay-cell-state-frontier",
            "cell-state-frontier-quality-gate",
            "evaluate-cell-state-frontier-scenarios",
            "cell-state-frontier-policy",
            "cell-state-frontier-contracts",
            "cell-state-frontier-schema",
            "cell-state-frontier-metrics",
            "build-cell-state-frontier-bundle",
            "cell-state-frontier-lineage",
            "cell-state-frontier-reconciliation",
            "cell-state-frontier-review-view",
            "cell-state-frontier-trace",
            "run-cell-state-frontier-pipeline",
            "build-cell-state-frontier-release",
        )
        text_commands = (
            "export-cell-state-frontier-receipts-csv",
            "export-cell-state-frontier-review-csv",
            "export-cell-state-frontier-review-markdown",
            "export-cell-state-frontier-metrics-csv",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, command in enumerate(json_commands):
                output = root / f"{index}-{command}.json"
                arguments = [command]
                if command == "run-cell-state-frontier-pipeline":
                    arguments.extend(("--run-id", "d08-cli", "--fail-on-review"))
                if command in {"cell-state-frontier-trace", "build-cell-state-frontier-release"}:
                    arguments.extend(("--run-id", f"d08-{index}"))
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

    def test_domain_08_cli_accepts_checked_in_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.json"
            output = root / "evaluation.json"
            source.write_text(json.dumps(default_cell_state_frontier_fixture().to_dict()), encoding="utf-8")
            self.assertEqual(main(["evaluate-cell-state-frontier-fixture", str(source), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(len(payload["receipts"]), 16)
            self.assertEqual(len(payload["checks"]), 120)


if __name__ == "__main__":
    unittest.main()
