"""Command-line coverage for the Domain 11 causal frontier."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CausalFrontierCliTests(unittest.TestCase):
    def run_cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "glio_noncode", command, *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_json_cli(self, command: str, *arguments: str) -> dict[str, object]:
        result = self.run_cli(command, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)
        return payload

    def test_data_audit_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-data-audit")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["failed_check_ids"], [])

    def test_contract_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-contracts")
        self.assertEqual(len(payload["contracts"]), 4)
        self.assertTrue(payload["content_address"].startswith("sha256:"))

    def test_schema_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-schema")
        self.assertEqual(len(payload["operations"]), 4)
        self.assertEqual(payload["version"], "2026.08.d11.v1")

    def test_evaluate_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-evaluate")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_checks"], 120)
        self.assertEqual(len(payload["executions"]), 16)

    def test_replay_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-replay")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["check_count"], 120)
        self.assertEqual(payload["passed_check_count"], 120)

    def test_metrics_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-metrics")
        self.assertEqual(len(payload["metrics"]), 13)
        self.assertTrue(payload["content_address"].startswith("sha256:"))

    def test_lineage_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-lineage")
        self.assertTrue(payload["acyclic"])
        self.assertEqual(len(payload["edges"]), 36)
        self.assertEqual(len(payload["terminal_addresses"]), 16)

    def test_policy_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-policy")
        self.assertEqual(len(payload["decisions"]), 4)
        self.assertEqual(len(payload["policy"]["rules"]), 4)

    def test_quality_gate_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-quality-gate")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_count"], 12)

    def test_runtime_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-runtime")
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["stages"]), 10)

    def test_release_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-release")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["state"], "ready")
        self.assertEqual(len(payload["checks"]), 4)

    def test_depth_command(self) -> None:
        payload = self.run_json_cli("causal-frontier-depth-audit")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_count"], 18)

    def test_json_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evaluation.json"
            result = self.run_cli("causal-frontier-evaluate", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(payload["accepted"])

    def test_csv_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review.csv"
            result = self.run_cli("export-causal-frontier-review-csv", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            text = output.read_text(encoding="utf-8")
        self.assertEqual(len(text.splitlines()), 17)
        self.assertIn("record_id,operation,role,state", text)
        self.assertIn("C16-POS-001", text)

    def test_command_accepts_fixture_input(self) -> None:
        fixture = self.run_json_cli("causal-frontier-evaluate")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps({
                "fixture_id": "causal-frontier-public-aggregate",
                "fixture_version": "2026.08.d11-c13-c16.v1",
                "context_key": "GRCh38|glioma|adult|stem_like|core|unknown",
                "evidence_boundary": "public_aggregate_non_patient",
                "sources": [],
                "records": [],
            }), encoding="utf-8")
            result = self.run_cli("causal-frontier-data-audit", str(path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("causal fixture requires sources and records", result.stderr)
        self.assertTrue(fixture["accepted"])


if __name__ == "__main__":
    unittest.main()
