from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "identity-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class IdentityFixtureCliTests(unittest.TestCase):
    def _run(self, root: Path, name: str, command: str) -> dict[str, object]:
        output = root / f"{name}.json"
        arguments = [command, str(FIXTURE), "--output", str(output)]
        if command == "replay-identity-fixtures":
            arguments = [
                command,
                str(FIXTURE),
                "--required-context-key",
                CONTEXT,
                "--output",
                str(output),
            ]
        self.assertEqual(main(arguments), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_data_fixture_replay_quality_and_scenarios_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self._run(root, "data", "audit-identity-data")
            fixture = self._run(root, "fixture", "evaluate-identity-fixture")
            replay = self._run(root, "replay", "replay-identity-fixtures")
            quality = self._run(root, "quality", "identity-quality-gate")
            scenarios = self._run(root, "scenarios", "evaluate-identity-scenarios")
            self.assertTrue(data["accepted"])
            self.assertTrue(fixture["passed"])
            self.assertTrue(replay["passed"])
            self.assertTrue(quality["passed"])
            self.assertTrue(scenarios["passed"])
            self.assertEqual(fixture["check_count"], 37)
            self.assertEqual(scenarios["scenario_count"], 12)

    def test_contract_and_bundle_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts_path = root / "contracts.json"
            bundle_path = root / "bundle.json"
            self.assertEqual(
                main(["identity-contracts", "--output", str(contracts_path)]),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "build-identity-bundle",
                        str(FIXTURE),
                        "--output",
                        str(bundle_path),
                    ]
                ),
                0,
            )
            contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(contracts["contract_count"], 4)
            self.assertTrue(bundle["accepted"])
            self.assertEqual(bundle["entry_count"], 12)

    def test_bundle_cli_supports_markdown_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "identity.md"
            csv = root / "identity.csv"
            self.assertEqual(
                main(
                    [
                        "build-identity-bundle",
                        str(FIXTURE),
                        "--output",
                        str(markdown),
                        "--format",
                        "markdown",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "build-identity-bundle",
                        str(FIXTURE),
                        "--output",
                        str(csv),
                        "--format",
                        "csv",
                    ]
                ),
                0,
            )
            self.assertTrue(markdown.read_text(encoding="utf-8").startswith("# Identity"))
            self.assertEqual(len(csv.read_text(encoding="utf-8").splitlines()), 13)

    def test_help_registers_all_identity_commands(self) -> None:
        parser = __import__("glio_noncode.cli", fromlist=["build_parser"]).build_parser()
        commands = set(parser._subparsers._group_actions[0].choices)
        self.assertTrue(
            {
                "evaluate-identity-fixture",
                "audit-identity-data",
                "replay-identity-fixtures",
                "identity-quality-gate",
                "evaluate-identity-scenarios",
                "identity-contracts",
                "build-identity-bundle",
            }.issubset(commands)
        )


if __name__ == "__main__":
    unittest.main()
