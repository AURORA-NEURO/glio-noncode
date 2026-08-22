"""CLI coverage for the Domain 15 workspace frontier."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WorkspaceFrontierCliTests(unittest.TestCase):
    def run_cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "glio_noncode", command, *arguments], check=False, capture_output=True, text=True)

    def run_json_cli(self, command: str, *arguments: str) -> dict[str, object]:
        result = self.run_cli(command, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)
        return payload

    def test_audit_contract_schema_and_evaluation(self) -> None:
        audit = self.run_json_cli("workspace-frontier-data-audit")
        contracts = self.run_json_cli("workspace-frontier-contracts")
        schema = self.run_json_cli("workspace-frontier-schema")
        evaluation = self.run_json_cli("workspace-frontier-evaluate")
        self.assertTrue(audit["accepted"])
        self.assertEqual(len(contracts["contracts"]), 4)
        self.assertEqual(len(schema["operations"]), 4)
        self.assertEqual(schema["version"], "2026.08.d15.v1")
        self.assertTrue(evaluation["accepted"])
        self.assertEqual(evaluation["passed_checks"], 120)

    def test_replay_metrics_lineage_and_policy(self) -> None:
        replay = self.run_json_cli("workspace-frontier-replay")
        metrics = self.run_json_cli("workspace-frontier-metrics")
        lineage = self.run_json_cli("workspace-frontier-lineage")
        policy = self.run_json_cli("workspace-frontier-policy")
        self.assertTrue(replay["stable"])
        self.assertTrue(replay["evaluation_address"].startswith("sha256:"))
        self.assertEqual(len(metrics["metrics"]), 13)
        self.assertTrue(lineage["acyclic"])
        self.assertEqual(len(lineage["edges"]), 36)
        self.assertEqual(len(policy["decisions"]), 16)

    def test_quality_runtime_bundle_artifacts_and_release(self) -> None:
        quality = self.run_json_cli("workspace-frontier-quality-gate")
        runtime = self.run_json_cli("workspace-frontier-runtime")
        bundle = self.run_json_cli("workspace-frontier-bundle")
        artifacts = self.run_json_cli("workspace-frontier-artifacts")
        release = self.run_json_cli("workspace-frontier-release")
        self.assertTrue(quality["accepted"])
        self.assertEqual(quality["passed_count"], 14)
        self.assertTrue(runtime["accepted"])
        self.assertEqual(len(runtime["stages"]), 8)
        self.assertTrue(bundle["accepted"])
        self.assertEqual(len(artifacts["artifacts"]), 7)
        self.assertTrue(release["accepted"])
        self.assertEqual(release["state"], "ready")

    def test_observability_depth_and_review_queue(self) -> None:
        observability = self.run_json_cli("workspace-frontier-observability")
        depth = self.run_json_cli("workspace-frontier-depth-audit")
        queue = self.run_json_cli("workspace-frontier-review-queue")
        self.assertEqual(len(observability["events"]), 24)
        self.assertTrue(observability["accepted"])
        self.assertTrue(depth["accepted"])
        self.assertEqual(depth["passed_count"], 21)
        self.assertTrue(queue["accepted"])
        self.assertEqual(queue["ready_count"], 3)
        self.assertEqual(queue["held_count"], 13)

    def test_adapter_scenario_threshold_and_invariant_commands(self) -> None:
        adapters = self.run_json_cli("workspace-frontier-adapters")
        scenarios = self.run_json_cli("workspace-frontier-scenarios")
        thresholds = self.run_json_cli("workspace-frontier-thresholds")
        invariants = self.run_json_cli("workspace-frontier-invariants")
        self.assertEqual(len(adapters["adapters"]), 4)
        self.assertEqual(len(scenarios["scenarios"]), 33)
        self.assertEqual(len(thresholds["probes"]), 972)
        self.assertTrue(invariants["accepted"])

    def test_csv_output_and_fixture_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "review.csv"
            result = self.run_cli("export-workspace-frontier-review-csv", "--output", str(csv_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            csv_text = csv_path.read_text(encoding="utf-8")
            invalid = root / "invalid.json"
            invalid.write_text(json.dumps({"fixture_id": "bad", "sources": [], "records": []}), encoding="utf-8")
            result = self.run_cli("workspace-frontier-data-audit", str(invalid))
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C04-POS-001", csv_text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace frontier fixture requires sources and records", result.stderr)


if __name__ == "__main__":
    unittest.main()
