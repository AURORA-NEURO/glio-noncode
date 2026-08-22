"""CLI coverage for the Domain 13 validation-planning frontier."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ValidationFrontierCliTests(unittest.TestCase):
    def run_cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "glio_noncode", command, *arguments], check=False, capture_output=True, text=True)

    def run_json_cli(self, command: str, *arguments: str) -> dict[str, object]:
        result = self.run_cli(command, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)
        return payload

    def test_audit_contract_schema_and_evaluation(self) -> None:
        audit = self.run_json_cli("validation-frontier-data-audit")
        contracts = self.run_json_cli("validation-frontier-contracts")
        schema = self.run_json_cli("validation-frontier-schema")
        evaluation = self.run_json_cli("validation-frontier-evaluate")
        self.assertTrue(audit["accepted"])
        self.assertEqual(len(contracts["contracts"]), 4)
        self.assertEqual(len(schema["operations"]), 4)
        self.assertEqual(schema["version"], "2026.08.d13.v1")
        self.assertTrue(evaluation["accepted"])
        self.assertEqual(evaluation["passed_checks"], 120)

    def test_replay_metrics_lineage_and_policy(self) -> None:
        replay = self.run_json_cli("validation-frontier-replay")
        metrics = self.run_json_cli("validation-frontier-metrics")
        lineage = self.run_json_cli("validation-frontier-lineage")
        policy = self.run_json_cli("validation-frontier-policy")
        self.assertTrue(replay["accepted"])
        self.assertEqual(replay["check_count"], 120)
        self.assertEqual(len(metrics["metrics"]), 13)
        self.assertTrue(lineage["acyclic"])
        self.assertEqual(len(lineage["edges"]), 36)
        self.assertEqual(len(policy["decisions"]), 4)

    def test_quality_runtime_bundle_artifacts_and_release(self) -> None:
        quality = self.run_json_cli("validation-frontier-quality-gate")
        runtime = self.run_json_cli("validation-frontier-runtime")
        bundle = self.run_json_cli("validation-frontier-bundle")
        artifacts = self.run_json_cli("validation-frontier-artifacts")
        release = self.run_json_cli("validation-frontier-release")
        self.assertTrue(quality["accepted"])
        self.assertEqual(quality["passed_count"], 12)
        self.assertTrue(runtime["accepted"])
        self.assertEqual(len(runtime["stages"]), 10)
        self.assertTrue(bundle["publishable"])
        self.assertEqual(len(artifacts["artifacts"]), 7)
        self.assertTrue(release["accepted"])
        self.assertEqual(release["state"], "ready")

    def test_observability_and_depth(self) -> None:
        observability = self.run_json_cli("validation-frontier-observability")
        depth = self.run_json_cli("validation-frontier-depth-audit")
        self.assertEqual(len(observability["events"]), 26)
        self.assertEqual(observability["counter_map"]["execution_count"], 16)
        self.assertTrue(depth["accepted"])
        self.assertEqual(depth["passed_count"], 20)

    def test_csv_output_and_fixture_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "review.csv"
            result = self.run_cli("export-validation-frontier-review-csv", "--output", str(csv_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            csv_text = csv_path.read_text(encoding="utf-8")
            invalid = root / "invalid.json"
            invalid.write_text(json.dumps({"fixture_id": "bad", "sources": [], "records": []}), encoding="utf-8")
            result = self.run_cli("validation-frontier-data-audit", str(invalid))
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C04-POS-001", csv_text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("validation frontier fixture requires sources and records", result.stderr)


if __name__ == "__main__":
    unittest.main()
