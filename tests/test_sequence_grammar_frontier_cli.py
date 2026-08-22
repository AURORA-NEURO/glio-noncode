from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.sequence_grammar_frontier_cli import (
    SEQUENCE_GRAMMAR_FRONTIER_COMMANDS,
    run_sequence_grammar_operation,
)
from glio_noncode.sequence_grammar_frontier_public_data import default_sequence_grammar_fixture


class SequenceGrammarFrontierCliTests(unittest.TestCase):
    def test_command_surface_is_closed(self) -> None:
        self.assertEqual(len(SEQUENCE_GRAMMAR_FRONTIER_COMMANDS), 25)
        for command in SEQUENCE_GRAMMAR_FRONTIER_COMMANDS:
            result = run_sequence_grammar_operation(command)
            if command == "export-sequence-grammar-review-csv":
                self.assertIn("record_id", result)
            else:
                self.assertTrue(hasattr(result, "to_dict"))

    def test_cli_accepts_fixture_input_and_csv_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture_path = root / "fixture.json"
            output_path = root / "review.csv"
            fixture_path.write_text(
                json.dumps(default_sequence_grammar_fixture().to_dict(include_payload=True)),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "sequence-grammar-data-audit",
                        str(fixture_path),
                        "--output",
                        str(root / "audit.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "export-sequence-grammar-review-csv",
                        str(fixture_path),
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            self.assertIn("C08-CTRL-001", output_path.read_text(encoding="utf-8"))

    def test_cli_pipeline_emits_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "pipeline.json"
            self.assertEqual(
                main(
                    [
                        "sequence-grammar-pipeline",
                        "--run-id",
                        "grammar-cli",
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(len(payload["runtime"]["stages"]), 10)
            self.assertEqual(len(payload["view"]["entries"]), 16)


if __name__ == "__main__":
    unittest.main()
