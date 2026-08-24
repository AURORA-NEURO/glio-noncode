"""CLI coverage for the module-fabric integration surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "glio_noncode", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class ModuleFabricCliTests(unittest.TestCase):
    def test_fixture_and_data_commands(self) -> None:
        fixture = run_cli("module-fabric-fixture")
        self.assertEqual(fixture.returncode, 0, fixture.stderr)
        payload = json.loads(fixture.stdout)
        self.assertEqual(len(payload["records"]), 32)
        data = run_cli("module-fabric-data-audit")
        self.assertEqual(data.returncode, 0, data.stderr)
        self.assertTrue(json.loads(data.stdout)["accepted"])

    def test_evaluate_depth_quality_and_replay(self) -> None:
        for command in ("module-fabric-evaluate", "module-fabric-depth", "module-fabric-quality", "module-fabric-replay", "module-fabric-scenarios"):
            result = run_cli(command)
            self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            self.assertTrue(json.loads(result.stdout)["accepted"], command)

    def test_compliance_and_check_projection_commands(self) -> None:
        compliance = run_cli("module-fabric-compliance")
        self.assertEqual(compliance.returncode, 0, compliance.stderr)
        self.assertEqual(json.loads(compliance.stdout)["passed_checks"], 12)
        checks = run_cli("module-fabric-checks-csv")
        self.assertEqual(checks.returncode, 0, checks.stderr)
        self.assertEqual(len(checks.stdout.splitlines()), 395)

    def test_runtime_and_report_formats(self) -> None:
        runtime = run_cli("module-fabric-runtime")
        self.assertEqual(runtime.returncode, 0, runtime.stderr)
        self.assertEqual(json.loads(runtime.stdout)["state"], "accepted")
        report = run_cli("module-fabric-report", "--format", "markdown")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("# Module Fabric Runtime Report", report.stdout)

    def test_csv_and_failure_commands(self) -> None:
        csv = run_cli("module-fabric-review-csv")
        self.assertEqual(csv.returncode, 0, csv.stderr)
        self.assertEqual(len(csv.stdout.splitlines()), 33)
        failures = run_cli("module-fabric-failures")
        self.assertEqual(failures.returncode, 0, failures.stderr)
        self.assertTrue(json.loads(failures.stdout)["accepted"])

    def test_static_contract_commands(self) -> None:
        for command in ("module-fabric-schema", "module-fabric-catalog", "module-fabric-sources", "module-fabric-data-dictionary"):
            result = run_cli(command)
            self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            self.assertTrue(json.loads(result.stdout))

    def test_checked_in_fixture_input_is_accepted(self) -> None:
        fixture = str(ROOT / "examples" / "module-fabric-public-aggregate.json")
        result = run_cli("module-fabric-evaluate", "--input", fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["accepted"])

    def test_output_paths_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runtime.json"
            result = run_cli("module-fabric-runtime", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["state"], "accepted")


if __name__ == "__main__":
    unittest.main()
