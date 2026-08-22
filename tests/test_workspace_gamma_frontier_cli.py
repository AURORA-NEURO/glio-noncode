from __future__ import annotations

import contextlib
import io
import json
import unittest

from glio_noncode.cli import main


class WorkspaceGammaFrontierCliTests(unittest.TestCase):
    def _run_json(self, command: str) -> dict:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            result = main([command])
        self.assertEqual(result, 0)
        return json.loads(stream.getvalue())

    def test_data_contract_schema_and_evaluate_commands(self) -> None:
        self.assertTrue(self._run_json("gamma-frontier-data-audit")["accepted"])
        self.assertEqual(len(self._run_json("gamma-frontier-contracts")["contracts"]), 4)
        self.assertEqual(len(self._run_json("gamma-frontier-schema")["operations"]), 4)
        self.assertTrue(self._run_json("gamma-frontier-evaluate")["accepted"])

    def test_replay_runtime_quality_and_pipeline_commands(self) -> None:
        self.assertTrue(self._run_json("gamma-frontier-replay")["accepted"])
        self.assertTrue(self._run_json("gamma-frontier-runtime")["accepted"])
        self.assertTrue(self._run_json("gamma-frontier-quality-gate")["accepted"])
        payload = self._run_json("gamma-frontier-pipeline")
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["release"]["state"], "ready")

    def test_supporting_review_commands_emit_structured_outputs(self) -> None:
        self.assertEqual(len(self._run_json("gamma-frontier-metrics")["metrics"]), 17)
        self.assertIn("edges", self._run_json("gamma-frontier-lineage"))
        self.assertIn("decisions", self._run_json("gamma-frontier-policy"))
        self.assertTrue(self._run_json("gamma-frontier-compliance")["accepted"])
        self.assertTrue(self._run_json("gamma-frontier-accessibility")["accepted"])
        self.assertTrue(self._run_json("gamma-frontier-invariants")["accepted"])
        self.assertEqual(len(self._run_json("gamma-frontier-scenarios")["scenarios"]), 20)
        self.assertTrue(self._run_json("gamma-frontier-thresholds")["accepted"])
        self.assertTrue(self._run_json("gamma-frontier-validation")["accepted"])
        self.assertEqual(len(self._run_json("gamma-frontier-runbook")["steps"]), 14)

    def test_csv_export_is_stable(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            result = main(["export-gamma-frontier-review-csv"])
        self.assertEqual(result, 0)
        self.assertTrue(stream.getvalue().startswith("row_id,record_id,operation"))
        self.assertEqual(stream.getvalue().count("\n"), 17)


if __name__ == "__main__":
    unittest.main()
