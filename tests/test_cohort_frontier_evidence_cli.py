"""Command-line coverage for the Domain 12 cohort frontier."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CohortFrontierCliTests(unittest.TestCase):
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
        payload = self.run_json_cli("cohort-frontier-data-audit")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["failed_check_ids"], [])

    def test_contract_and_schema_commands(self) -> None:
        contracts = self.run_json_cli("cohort-frontier-contracts")
        schema = self.run_json_cli("cohort-frontier-schema")
        self.assertEqual(len(contracts["contracts"]), 4)
        self.assertEqual(len(schema["operations"]), 4)
        self.assertEqual(schema["version"], "2026.08.d12.v1")

    def test_evaluation_and_replay_commands(self) -> None:
        evaluation = self.run_json_cli("cohort-frontier-evaluate")
        replay = self.run_json_cli("cohort-frontier-replay")
        self.assertTrue(evaluation["accepted"])
        self.assertEqual(evaluation["passed_checks"], 120)
        self.assertEqual(len(evaluation["executions"]), 16)
        self.assertTrue(replay["accepted"])
        self.assertEqual(replay["check_count"], 120)
        self.assertEqual(replay["passed_check_count"], 120)

    def test_metrics_lineage_and_policy_commands(self) -> None:
        metrics = self.run_json_cli("cohort-frontier-metrics")
        lineage = self.run_json_cli("cohort-frontier-lineage")
        policy = self.run_json_cli("cohort-frontier-policy")
        self.assertEqual(len(metrics["metrics"]), 11)
        self.assertTrue(lineage["acyclic"])
        self.assertEqual(len(lineage["edges"]), 36)
        self.assertEqual(len(policy["decisions"]), 4)
        self.assertEqual(len(policy["policy"]["rules"]), 4)

    def test_quality_runtime_bundle_and_release_commands(self) -> None:
        quality = self.run_json_cli("cohort-frontier-quality-gate")
        runtime = self.run_json_cli("cohort-frontier-runtime")
        bundle = self.run_json_cli("cohort-frontier-bundle")
        release = self.run_json_cli("cohort-frontier-release")
        self.assertTrue(quality["accepted"])
        self.assertEqual(quality["passed_count"], 12)
        self.assertTrue(runtime["accepted"])
        self.assertEqual(len(runtime["stages"]), 10)
        self.assertTrue(bundle["publishable"])
        self.assertTrue(release["accepted"])
        self.assertEqual(release["state"], "ready")
        self.assertEqual(len(release["checks"]), 4)

    def test_depth_command(self) -> None:
        payload = self.run_json_cli("cohort-frontier-depth-audit")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_count"], 19)

    def test_json_and_csv_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_output = root / "evaluation.json"
            csv_output = root / "review.csv"
            result = self.run_cli("cohort-frontier-evaluate", "--output", str(json_output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            result = self.run_cli("export-cohort-frontier-review-csv", "--output", str(csv_output))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(json_output.read_text(encoding="utf-8"))
            csv_text = csv_output.read_text(encoding="utf-8")
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("record_id,operation,role,state", csv_text)
        self.assertIn("C16-POS-001", csv_text)

    def test_command_accepts_fixture_input(self) -> None:
        evaluation = self.run_json_cli("cohort-frontier-evaluate")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(
                json.dumps(
                    {
                        "fixture_id": "cohort-frontier-public-aggregate",
                        "fixture_version": "2026.08.d12-c13-c16.v1",
                        "context_key": "GRCh38|glioma|adult|stem_like|core|unknown",
                        "evidence_boundary": "public_aggregate_non_patient",
                        "sources": [],
                        "records": [],
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_cli("cohort-frontier-data-audit", str(path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cohort frontier fixture requires sources and records", result.stderr)
        self.assertTrue(evaluation["accepted"])


if __name__ == "__main__":
    unittest.main()
