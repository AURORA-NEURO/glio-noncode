from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class SequenceFrontierEvidenceCliTests(unittest.TestCase):
    def _run_json(self, root: Path, command: str, *arguments: str) -> dict:
        output = root / f"{command}.json"
        self.assertEqual(main([command, *arguments, "--output", str(output)]), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def _run_text(self, root: Path, command: str) -> str:
        output = root / f"{command}.txt"
        self.assertEqual(main([command, "--output", str(output)]), 0)
        return output.read_text(encoding="utf-8")

    def test_fixture_audit_replay_quality_scenarios_and_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(self._run_json(root, "evaluate-sequence-frontier-fixture")["accepted"])
            self.assertTrue(self._run_json(root, "audit-sequence-frontier-data")["accepted"])
            self.assertTrue(self._run_json(root, "replay-sequence-frontier")["accepted"])
            self.assertTrue(self._run_json(root, "sequence-frontier-quality-gate")["accepted"])
            self.assertTrue(
                self._run_json(root, "evaluate-sequence-frontier-scenarios")["accepted"]
            )
            self.assertTrue(self._run_json(root, "sequence-frontier-policy")["accepted"])

    def test_contract_schema_metrics_bundle_lineage_and_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                len(self._run_json(root, "sequence-frontier-contracts")["contracts"]), 4
            )
            schema = self._run_json(root, "sequence-frontier-schema")
            self.assertTrue(schema["validation"]["accepted"])
            self.assertEqual(len(schema["validation"]["checks"]), 23)
            self.assertEqual(self._run_json(root, "sequence-frontier-metrics")["total_records"], 16)
            self.assertTrue(self._run_json(root, "build-sequence-frontier-bundle")["accepted"])
            self.assertTrue(self._run_json(root, "sequence-frontier-lineage")["accepted"])
            self.assertTrue(self._run_json(root, "sequence-frontier-reconciliation")["accepted"])

    def test_runtime_release_view_trace_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = self._run_json(
                root, "run-sequence-frontier-pipeline", "--run-id", "sequence-cli-runtime"
            )
            self.assertTrue(runtime["accepted"])
            self.assertTrue(
                self._run_json(
                    root, "build-sequence-frontier-release", "--run-id", "sequence-cli-release"
                )["accepted"]
            )
            view = self._run_json(root, "sequence-frontier-review-view")
            self.assertTrue(view["accepted"])
            self.assertEqual(view["review_count"], 12)
            trace = self._run_json(
                root, "sequence-frontier-trace", "--run-id", "sequence-cli-trace"
            )
            self.assertTrue(trace["accepted"])
            self.assertEqual(len(trace["stage_receipts"]), 9)
            self.assertEqual(
                self._run_text(root, "export-sequence-frontier-receipts-csv").count("\n"), 17
            )
            self.assertEqual(
                self._run_text(root, "export-sequence-frontier-review-csv").count("\n"), 13
            )
            self.assertIn(
                "C13-CTRL-003", self._run_text(root, "export-sequence-frontier-review-markdown")
            )
            self.assertEqual(
                self._run_text(root, "export-sequence-frontier-metrics-csv").count("\n"), 5
            )


if __name__ == "__main__":
    unittest.main()
