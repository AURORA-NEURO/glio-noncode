from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class CausalAlphaFrontierCliTests(unittest.TestCase):
    def _run_json(self, command: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.json"
            self.assertEqual(main([command, "--output", str(output)]), 0)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_data_audit_command(self) -> None:
        payload = self._run_json("causal-alpha-frontier-data-audit")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["record_count"], 16)
        self.assertEqual(payload["source_count"], 5)

    def test_contract_schema_and_evaluation_commands(self) -> None:
        contracts = self._run_json("causal-alpha-frontier-contracts")
        schema = self._run_json("causal-alpha-frontier-schema")
        evaluation = self._run_json("causal-alpha-frontier-evaluate")
        self.assertTrue(contracts["accepted"])
        self.assertEqual(len(contracts["contracts"]), 4)
        self.assertTrue(schema["accepted"])
        self.assertEqual(schema["record_count"], 16)
        self.assertTrue(evaluation["accepted"])
        self.assertEqual(len(evaluation["evaluation"]["results"]), 16)

    def test_runtime_command_exposes_all_stages(self) -> None:
        payload = self._run_json("causal-alpha-frontier-runtime")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["stage_count"], 31)
        self.assertEqual(payload["stage_ids"][-1], "runbook")
        self.assertEqual(payload["release"]["state"], "ready")

    def test_operational_and_boundary_commands(self) -> None:
        operational = self._run_json("causal-alpha-frontier-operational")
        boundary = self._run_json("causal-alpha-frontier-boundary")
        self.assertTrue(operational["accepted"])
        self.assertEqual(operational["allowed_count"], 3)
        self.assertEqual(operational["review_count"], 9)
        self.assertEqual(operational["quarantine_count"], 4)
        self.assertTrue(boundary["accepted"])
        self.assertIn("causal identification", boundary["excluded_claims"])

    def test_release_artifacts_assurance_and_runbook_commands(self) -> None:
        release = self._run_json("causal-alpha-frontier-release")
        artifacts = self._run_json("causal-alpha-frontier-artifacts")
        assurance = self._run_json("causal-alpha-frontier-assurance")
        runbook = self._run_json("causal-alpha-frontier-runbook")
        self.assertTrue(release["accepted"])
        self.assertEqual(release["state"], "ready")
        self.assertTrue(artifacts["accepted"])
        self.assertEqual(artifacts["resolved_count"], 19)
        self.assertTrue(assurance["accepted"])
        self.assertTrue(runbook["accepted"])
        self.assertEqual(len(runbook["steps"]), 12)

    def test_markdown_exports_are_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "review.md"
            csv = root / "review.csv"
            self.assertEqual(main(["causal-alpha-frontier-review-view", "--output", str(review)]), 0)
            self.assertEqual(main(["export-causal-alpha-frontier-review-markdown", "--output", str(review)]), 0)
            self.assertEqual(main(["export-causal-alpha-frontier-review-csv", "--output", str(csv)]), 0)
            self.assertIn("| Record | Operation |", review.read_text(encoding="utf-8"))
            self.assertIn("| Record | Operation |", csv.read_text(encoding="utf-8"))

    def test_export_json_command_has_six_envelopes(self) -> None:
        payload = self._run_json("export-causal-alpha-frontier-json")
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["envelopes"]), 10)
        self.assertEqual({item["export_id"] for item in payload["envelopes"]}, {"fixture", "evaluation", "controls", "traces", "projections", "diagnostics", "summary", "review-csv", "review-markdown", "release"})


if __name__ == "__main__":
    unittest.main()
