"""CLI coverage for the Domain 14 evidence lifecycle frontier."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class EvidenceLifecycleFrontierCliTests(unittest.TestCase):
    def run_cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "glio_noncode", command, *arguments], check=False, capture_output=True, text=True)

    def run_json_cli(self, command: str, *arguments: str) -> dict[str, object]:
        result = self.run_cli(command, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)
        return payload

    def test_audit_contract_schema_and_evaluation(self) -> None:
        audit = self.run_json_cli("evidence-lifecycle-data-audit")
        contracts = self.run_json_cli("evidence-lifecycle-contracts")
        schema = self.run_json_cli("evidence-lifecycle-schema")
        evaluation = self.run_json_cli("evidence-lifecycle-evaluate")
        self.assertTrue(audit["accepted"])
        self.assertEqual(len(contracts["contracts"]), 4)
        self.assertEqual(len(schema["operations"]), 4)
        self.assertEqual(schema["version"], "2026.08.d14.v1")
        self.assertTrue(evaluation["accepted"])
        self.assertEqual(evaluation["passed_checks"], 120)

    def test_replay_metrics_lineage_and_policy(self) -> None:
        replay = self.run_json_cli("evidence-lifecycle-replay")
        metrics = self.run_json_cli("evidence-lifecycle-metrics")
        lineage = self.run_json_cli("evidence-lifecycle-lineage")
        policy = self.run_json_cli("evidence-lifecycle-policy")
        self.assertTrue(replay["accepted"])
        self.assertTrue(replay["evaluation_address"].startswith("sha256:"))
        self.assertEqual(len(metrics["metrics"]), 13)
        self.assertTrue(lineage["acyclic"])
        self.assertEqual(len(lineage["edges"]), 36)
        self.assertEqual(len(policy["decisions"]), 4)

    def test_quality_runtime_bundle_artifacts_and_release(self) -> None:
        quality = self.run_json_cli("evidence-lifecycle-quality-gate")
        runtime = self.run_json_cli("evidence-lifecycle-runtime")
        bundle = self.run_json_cli("evidence-lifecycle-bundle")
        artifacts = self.run_json_cli("evidence-lifecycle-artifacts")
        release = self.run_json_cli("evidence-lifecycle-release")
        self.assertTrue(quality["accepted"])
        self.assertEqual(quality["passed_count"], 12)
        self.assertTrue(runtime["accepted"])
        self.assertEqual(len(runtime["stages"]), 10)
        self.assertTrue(bundle["publishable"])
        self.assertEqual(len(artifacts["artifacts"]), 7)
        self.assertTrue(release["accepted"])
        self.assertEqual(release["state"], "ready")

    def test_observability_depth_and_review_queue(self) -> None:
        observability = self.run_json_cli("evidence-lifecycle-observability")
        depth = self.run_json_cli("evidence-lifecycle-depth-audit")
        queue = self.run_json_cli("evidence-lifecycle-review-queue")
        self.assertEqual(len(observability["events"]), 26)
        self.assertEqual(observability["counters"]["execution_count"], 16)
        self.assertTrue(depth["accepted"])
        self.assertEqual(depth["passed_count"], 20)
        self.assertTrue(queue["accepted"])
        self.assertEqual(queue["ready_count"], 4)
        self.assertEqual(queue["blocked_count"], 12)

    def test_csv_output_and_fixture_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "review.csv"
            result = self.run_cli("export-evidence-lifecycle-review-csv", "--output", str(csv_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            csv_text = csv_path.read_text(encoding="utf-8")
            invalid = root / "invalid.json"
            invalid.write_text(json.dumps({"fixture_id": "bad", "sources": [], "records": []}), encoding="utf-8")
            result = self.run_cli("evidence-lifecycle-data-audit", str(invalid))
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C04-POS-001", csv_text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence lifecycle fixture requires sources and records", result.stderr)


if __name__ == "__main__":
    unittest.main()
