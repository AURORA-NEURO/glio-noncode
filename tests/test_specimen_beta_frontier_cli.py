from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

FIXTURE = Path("examples/specimen-beta-frontier-public-aggregate.json")
PIPELINE = Path("examples/specimen-beta-frontier-pipeline-accepted.json")


class SpecimenBetaFrontierCliTests(unittest.TestCase):
    def _run(self, command: str, input_path: Path | None = FIXTURE, *arguments: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.json"
            args = [command]
            if input_path is not None:
                args.append(str(input_path))
            args.extend(arguments)
            args.extend(["--output", str(output)])
            self.assertEqual(main(args), 0)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_evaluate_fixture_command(self) -> None:
        result = self._run("evaluate-specimen-beta-frontier-fixture")
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["checks"]), 72)

    def test_audit_command(self) -> None:
        result = self._run("audit-specimen-beta-frontier-data")
        self.assertTrue(result["accepted"])

    def test_replay_command(self) -> None:
        result = self._run(
            "replay-specimen-beta-frontier-fixtures",
            FIXTURE,
            "--required-context-key",
            "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
        )
        self.assertTrue(result["passed"])

    def test_quality_and_scenario_commands(self) -> None:
        quality = self._run("specimen-beta-frontier-quality-gate")
        scenarios = self._run("evaluate-specimen-beta-frontier-scenarios")
        self.assertTrue(quality["passed"])
        self.assertTrue(scenarios["passed"])

    def test_contract_command(self) -> None:
        result = self._run("specimen-beta-frontier-contracts", None)
        self.assertEqual(result["contract_count"], 4)

    def test_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.json"
            self.assertEqual(
                main(
                    [
                        "build-specimen-beta-frontier-bundle",
                        str(FIXTURE),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["entry_count"], 12)

    def test_lineage_command(self) -> None:
        result = self._run("specimen-beta-frontier-lineage")
        self.assertTrue(result["audit"]["passed"])
        self.assertEqual(len(result["nodes"]), 29)

    def test_pipeline_command(self) -> None:
        result = self._run("run-specimen-beta-frontier-pipeline", PIPELINE)
        self.assertTrue(result["published"])
        self.assertEqual(len(result["stage_receipts"]), 4)


if __name__ == "__main__":
    unittest.main()
