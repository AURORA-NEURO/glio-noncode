from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from glio_noncode import cli
from glio_noncode._cli_index import COMMANDS, LEGACY_COMMANDS

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPOSITORY_ROOT / "src" / "glio_noncode" / "cli.py"


def _top_level_commands(parser: argparse.ArgumentParser) -> tuple[str, ...]:
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return tuple(sorted(str(name) for name in subparsers.choices))


class LightweightCliShellTests(unittest.TestCase):
    def test_help_version_and_index_are_isolated_from_legacy_module(self) -> None:
        script = f"""
import contextlib
import importlib.util
import io
import json
import sys
import types
from pathlib import Path

cli_path = Path({str(CLI_PATH)!r})
package = types.ModuleType("glio_noncode")
package.__path__ = [str(cli_path.parent)]
sys.modules["glio_noncode"] = package
spec = importlib.util.spec_from_file_location("glio_noncode.cli", cli_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
results = []
for argv in (["--help"], ["--version"], ["commands", "show", "case"]):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main(argv)
    results.append((code, output.getvalue(), "glio_noncode._legacy_cli" in sys.modules))
print(json.dumps(results))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        results = json.loads(completed.stdout)
        self.assertEqual([result[0] for result in results], [0, 0, 0])
        self.assertIn("usage: glio-noncode", results[0][1])
        self.assertRegex(results[1][1], r"^glio-noncode \d+\.\d+\.\d+\n$")
        self.assertIn("case\tprepare and run a case", results[2][1])
        self.assertEqual([result[2] for result in results], [False, False, False])

    def test_focused_commands_receive_raw_nested_arguments(self) -> None:
        calls: list[tuple[str, list[str]]] = []

        def fake_import(name: str) -> types.SimpleNamespace:
            label = name.rsplit(".", 1)[-1]
            return types.SimpleNamespace(
                main=lambda argv: calls.append((label, argv)) or 17,
            )

        with patch.object(cli.importlib, "import_module", side_effect=fake_import):
            self.assertEqual(cli.main(["case", "prepare", "--input", "case.json"]), 17)
            self.assertEqual(cli.main(["expression", "allelic", "--input", "rna.json"]), 17)
            self.assertEqual(cli.main(["report-capabilities", "--output", "-"]), 17)
            self.assertEqual(
                cli.main(["run-report", "run-1", "--audience", "public"]),
                17,
            )

        self.assertEqual(
            calls,
            [
                ("_cli_case", ["prepare", "--input", "case.json"]),
                ("_cli_expression", ["allelic", "--input", "rna.json"]),
                ("_cli_report", ["report-capabilities", "--output", "-"]),
                ("_cli_report", ["run-report", "run-1", "--audience", "public"]),
            ],
        )

    def test_unknown_token_delegates_without_index_rejection(self) -> None:
        received: list[list[str]] = []
        legacy = types.SimpleNamespace(main=lambda argv: received.append(argv) or 23)
        with patch.object(cli, "_legacy_module", return_value=legacy):
            code = cli.main(["future-command-not-yet-indexed", "--opaque", "value"])
        self.assertEqual(code, 23)
        self.assertEqual(
            received,
            [["future-command-not-yet-indexed", "--opaque", "value"]],
        )

    def test_index_is_sorted_unique_and_searches_long_commands(self) -> None:
        self.assertEqual(COMMANDS, tuple(sorted(COMMANDS)))
        self.assertEqual(len(COMMANDS), len({name for name, _ in COMMANDS}))
        longest_name = max(LEGACY_COMMANDS, key=lambda row: len(row[0]))[0]
        search_term = longest_name[-96:]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main(["commands", "search", search_term])
        self.assertEqual(code, 0)
        self.assertIn(f"{longest_name}\t", output.getvalue())

    def test_build_parser_has_exact_generated_legacy_command_parity(self) -> None:
        parser = cli.build_parser()
        indexed_names = tuple(name for name, _ in LEGACY_COMMANDS)
        self.assertEqual(_top_level_commands(parser), indexed_names)
        self.assertGreater(len(indexed_names), 4_000)

    def test_representative_legacy_command_remains_parseable(self) -> None:
        parser = cli.build_parser()
        parsed = parser.parse_args(["module-impact-schema"])
        self.assertEqual(parsed.command, "module-impact-schema")


if __name__ == "__main__":
    unittest.main()
