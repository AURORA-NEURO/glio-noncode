from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "variation-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class VariationFixtureCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "glio_noncode", *arguments],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_evaluate_command_writes_complete_variation_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "variation.json"
            result = self.run_cli(
                "evaluate-variation-fixture",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["check_count"], 29)
            self.assertEqual(payload["failed_count"], 0)
            self.assertEqual(payload["fixture_id"], "variation-public-aggregate-001")

    def test_evaluate_command_prints_json_without_output_path(self) -> None:
        result = self.run_cli("evaluate-variation-fixture", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["context_key"], CONTEXT)

    def test_data_audit_command_writes_public_boundary_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data.json"
            result = self.run_cli(
                "audit-variation-data",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["record_count"], 5)
            self.assertEqual(payload["sensitive_paths"], [])

    def test_replay_command_accepts_required_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            result = self.run_cli(
                "replay-variation-fixtures",
                str(FIXTURE),
                "--required-context-key",
                CONTEXT,
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["case_count"], 1)
            self.assertEqual(payload["context_keys"], [CONTEXT])

    def test_replay_command_rejects_duplicate_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            result = self.run_cli(
                "replay-variation-fixtures",
                str(FIXTURE),
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(payload["passed"])
            self.assertEqual(payload["case_count"], 2)
            self.assertTrue(payload["duplicate_fixture_ids"])

    def test_quality_gate_command_writes_reconciled_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "quality.json"
            result = self.run_cli(
                "variation-quality-gate",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["check_count"], 12)
            self.assertEqual(payload["component_receipts"]["fixture"]["check_count"], 29)

    def test_scenario_command_writes_ten_state_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scenarios.json"
            result = self.run_cli(
                "evaluate-variation-scenarios",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["scenario_count"], 10)
            self.assertEqual(len(payload["positive_scenario_ids"]), 5)
            self.assertEqual(len(payload["review_scenario_ids"]), 5)

    def test_contract_command_writes_five_operation_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            result = self.run_cli("variation-contracts", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["contract_count"], 5)
            self.assertEqual(len(payload["capability_ids"]), 5)
            self.assertRegex(payload["manifest_address"], r"^sha256:[0-9a-f]{64}$")

    def test_bundle_command_writes_compact_json_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.json"
            result = self.run_cli(
                "build-variation-bundle",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["entry_count"], 10)
            self.assertEqual(payload["contract_manifest"]["contract_count"], 5)

    def test_bundle_command_supports_markdown_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.txt"
            result = self.run_cli(
                "build-variation-bundle",
                str(FIXTURE),
                "--output",
                str(output),
                "--format",
                "markdown",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = output.read_text(encoding="utf-8")
            self.assertTrue(rendered.startswith("# Variation evidence bundle"))
            self.assertIn("dbsnp:rs121913502", rendered)

    def test_quality_gate_returns_nonzero_for_sensitive_fixture(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["records"][0]["payload"]["patient_id"] = "restricted"
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "sensitive.json"
            output_path = Path(directory) / "quality.json"
            input_path.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.run_cli(
                "variation-quality-gate",
                str(input_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["passed"])
            self.assertIn("public-data-audit", payload["failed_check_ids"])

    def test_evaluate_command_returns_nonzero_for_failed_positive_record(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["records"][0]["payload"]["alternate"] = "<DEL>"
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "failed.json"
            output_path = Path(directory) / "failed-output.json"
            input_path.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.run_cli(
                "evaluate-variation-fixture",
                str(input_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["passed"])
            self.assertIn("positive:dbsnp:rs121913502:vrs", payload["failed_check_ids"])

    def test_commands_do_not_emit_restricted_fixture_values(self) -> None:
        result = self.run_cli("evaluate-variation-fixture", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("patient_id", result.stdout)
        self.assertNotIn("mrn", result.stdout)
        self.assertNotIn("secret", result.stdout.casefold())


if __name__ == "__main__":
    unittest.main()
