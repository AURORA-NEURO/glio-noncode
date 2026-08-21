from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "frontier-glioma-case.json"


class FrontierFixtureCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "glio_noncode", *arguments],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_fixture_command_writes_complete_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "frontier.json"
            result = self.run_cli(
                "evaluate-frontier-fixture",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["state"], "accepted")
            self.assertEqual(payload["check_count"], 49)
            self.assertEqual(payload["failed_count"], 0)
            self.assertEqual(
                payload["context_key"],
                "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
            )

    def test_fixture_command_prints_json_when_output_is_omitted(self) -> None:
        result = self.run_cli("evaluate-frontier-fixture", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(
            payload["source_ids"],
            ["glioma-regulatory-reference", "regulatory-assay-contract-reference"],
        )

    def test_fixture_command_returns_nonzero_for_failed_fixture(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["pipelines"]["workbench"]["accessibility_surface"]["contrast"] = False
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "failed.json"
            output_path = Path(directory) / "failed-output.json"
            input_path.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.run_cli(
                "evaluate-frontier-fixture",
                str(input_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["passed"])
            self.assertIn("workbench:accessibility", payload["failed_check_ids"])

    def test_fixture_command_rejects_invalid_fixture_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "invalid.json"
            input_path.write_text("[]", encoding="utf-8")
            result = self.run_cli("evaluate-frontier-fixture", str(input_path))
            self.assertEqual(result.returncode, 2)
            self.assertIn("frontier fixture must be an object", result.stderr)

    def test_fixture_command_does_not_emit_signing_secret(self) -> None:
        result = self.run_cli("evaluate-frontier-fixture", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("fixture-signing-secret-v1", result.stdout)

    def test_data_audit_command_writes_source_and_context_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data.json"
            result = self.run_cli("audit-frontier-data", str(FIXTURE), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["record_count"], 10)
            self.assertEqual(payload["context_mismatch_ids"], [])

    def test_data_audit_command_returns_nonzero_for_sensitive_record(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["pipelines"]["validation"]["risk_records"][0]["patient_id"] = "blocked"
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "sensitive.json"
            output_path = Path(directory) / "sensitive-output.json"
            input_path.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.run_cli(
                "audit-frontier-data",
                str(input_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["accepted"])
            self.assertIn(
                "records[EGFR-regulatory-guide-01].patient_id", payload["sensitive_paths"]
            )

    def test_data_audit_command_prints_json_without_output_path(self) -> None:
        result = self.run_cli("audit-frontier-data", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["source_ids"],
            ["glioma-regulatory-reference", "regulatory-assay-contract-reference"],
        )

    def test_replay_command_accepts_required_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            result = self.run_cli(
                "replay-frontier-fixtures",
                str(FIXTURE),
                "--required-context-key",
                "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["case_count"], 1)

    def test_replay_command_returns_nonzero_for_duplicate_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            result = self.run_cli(
                "replay-frontier-fixtures",
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

    def test_frontier_contract_command_writes_operation_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contracts.json"
            result = self.run_cli("frontier-contracts", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["contract_count"], 79)
            self.assertEqual(payload["family_counts"]["release"], 17)
            self.assertEqual(len(payload["capability_ids"]), 16)

    def test_frontier_contract_command_prints_manifest_without_output_path(self) -> None:
        result = self.run_cli("frontier-contracts")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertRegex(payload["manifest_address"], r"^sha256:[0-9a-f]{64}$")

    def test_scenario_command_writes_state_transition_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scenarios.json"
            result = self.run_cli(
                "evaluate-frontier-scenarios",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["scenario_count"], 8)
            self.assertEqual(len(payload["accepted_scenario_ids"]), 4)
            self.assertEqual(len(payload["review_scenario_ids"]), 4)

    def test_scenario_command_returns_nonzero_for_mutated_positive_path(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["pipelines"]["validation"]["risk_records"][0]["context_key"] = "wrong-context"
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "mutated.json"
            output_path = Path(directory) / "mutated-output.json"
            input_path.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.run_cli(
                "evaluate-frontier-scenarios",
                str(input_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["passed"])
            self.assertEqual(payload["failed_scenario_ids"], ["validation-positive"])

    def test_quality_gate_command_writes_reconciled_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "quality.json"
            result = self.run_cli(
                "frontier-quality-gate",
                str(FIXTURE),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["check_count"], 12)
            self.assertEqual(payload["component_receipts"]["contracts"]["contract_count"], 79)

    def test_quality_gate_command_returns_nonzero_for_sensitive_fixture(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["pipelines"]["validation"]["risk_records"][0]["patient_id"] = "blocked"
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "sensitive.json"
            output_path = Path(directory) / "quality.json"
            input_path.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.run_cli(
                "frontier-quality-gate",
                str(input_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["passed"])
            self.assertIn("public-data-audit", payload["failed_check_ids"])


if __name__ == "__main__":
    unittest.main()
