from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class FrontierAtlasEvidenceCliTests(unittest.TestCase):
    def _run_json(self, root: Path, command: str, *arguments: str) -> dict:
        output = root / f"{command}.json"
        self.assertEqual(main([command, *arguments, "--output", str(output)]), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def _run_text(self, root: Path, command: str) -> str:
        output = root / f"{command}.txt"
        self.assertEqual(main([command, "--output", str(output)]), 0)
        return output.read_text(encoding="utf-8")

    def test_fixture_audit_replay_quality_and_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluation = self._run_json(root, "evaluate-frontier-atlas-fixture")
            self.assertTrue(evaluation["accepted"])
            self.assertEqual(len(evaluation["checks"]), 120)
            audit = self._run_json(root, "audit-frontier-atlas-data")
            self.assertTrue(audit["accepted"])
            replay = self._run_json(root, "replay-frontier-atlas")
            self.assertTrue(replay["accepted"])
            quality = self._run_json(root, "frontier-atlas-quality-gate")
            self.assertTrue(quality["accepted"])
            scenarios = self._run_json(root, "evaluate-frontier-atlas-scenarios")
            self.assertTrue(scenarios["accepted"])
            policy = self._run_json(root, "frontier-atlas-policy")
            self.assertTrue(policy["accepted"])

    def test_contract_schema_metrics_bundle_lineage_and_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts = self._run_json(root, "frontier-atlas-contracts")
            self.assertEqual(len(contracts["contracts"]), 4)
            schema = self._run_json(root, "frontier-atlas-schema")
            self.assertTrue(schema["validation"]["accepted"])
            self.assertEqual(len(schema["validation"]["checks"]), 23)
            metrics = self._run_json(root, "frontier-atlas-metrics")
            self.assertEqual(metrics["total_records"], 16)
            bundle = self._run_json(root, "build-frontier-atlas-bundle")
            self.assertTrue(bundle["accepted"])
            lineage = self._run_json(root, "frontier-atlas-lineage")
            self.assertTrue(lineage["accepted"])
            reconciliation = self._run_json(root, "frontier-atlas-reconciliation")
            self.assertTrue(reconciliation["accepted"])

    def test_runtime_release_view_trace_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = self._run_json(root, "run-frontier-atlas-pipeline", "--run-id", "cli-runtime")
            self.assertTrue(runtime["accepted"])
            release = self._run_json(
                root, "build-frontier-atlas-release", "--run-id", "cli-release"
            )
            self.assertTrue(release["accepted"])
            view = self._run_json(root, "frontier-atlas-review-view")
            self.assertTrue(view["accepted"])
            self.assertEqual(view["review_count"], 12)
            trace = self._run_json(root, "frontier-atlas-trace", "--run-id", "cli-trace")
            self.assertTrue(trace["accepted"])
            self.assertEqual(len(trace["stage_receipts"]), 9)
            receipts = self._run_text(root, "export-frontier-atlas-receipts-csv")
            self.assertEqual(receipts.count("\n"), 17)
            review = self._run_text(root, "export-frontier-atlas-review-csv")
            self.assertEqual(review.count("\n"), 13)
            markdown = self._run_text(root, "export-frontier-atlas-review-markdown")
            self.assertIn("C13-CTRL-003", markdown)
            metrics = self._run_text(root, "export-frontier-atlas-metrics-csv")
            self.assertEqual(metrics.count("\n"), 5)


if __name__ == "__main__":
    unittest.main()
