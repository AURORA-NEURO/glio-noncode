from __future__ import annotations

import json
import subprocess
import sys
import unittest


class EvidenceReleaseFrontierCliTests(unittest.TestCase):
    def run_command(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "glio_noncode", command], capture_output=True, text=True, check=False)

    def test_data_audit_command(self) -> None:
        result = self.run_command("evidence-release-frontier-data-audit")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["accepted"])

    def test_evaluation_command(self) -> None:
        result = self.run_command("evidence-release-frontier-evaluate")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_checks"], 81)

    def test_pipeline_command(self) -> None:
        result = self.run_command("evidence-release-frontier-pipeline")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["stages"]), 53)

    def test_csv_command_has_stable_header(self) -> None:
        result = self.run_command("evidence-release-frontier-review-csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("record_id,capability,operation,role,state,issue_codes,content_address"))


if __name__ == "__main__":
    unittest.main()
