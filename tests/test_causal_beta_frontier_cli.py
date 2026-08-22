from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from glio_noncode.cli import main


class CausalBetaFrontierCliTests(unittest.TestCase):
    def _run_json(self, root: Path, command: str) -> dict[str, object]:
        output = root / f"{command}.json"
        self.assertEqual(main([command, "--output", str(output)]), 0)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict)
        return payload

    def test_data_audit_command_emits_pinned_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = self._run_json(Path(directory), "causal-beta-frontier-data-audit")
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["record_count"], 16)
            self.assertEqual(payload["source_count"], 5)
            self.assertEqual(payload["positive_count"], 4)
            self.assertEqual(payload["control_count"], 12)

    def test_contract_schema_evaluation_and_metrics_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contracts = self._run_json(root, "causal-beta-frontier-contracts")
            schema = self._run_json(root, "causal-beta-frontier-schema")
            evaluation = self._run_json(root, "causal-beta-frontier-evaluate")
            metrics = self._run_json(root, "causal-beta-frontier-metrics")
            self.assertTrue(contracts["accepted"])
            self.assertEqual(len(contracts["contracts"]), 4)
            self.assertTrue(schema["accepted"])
            self.assertEqual(len(schema["fields"]), 10)
            self.assertTrue(evaluation["accepted"])
            self.assertEqual(evaluation["state_match_count"], 16)
            self.assertEqual(metrics["record_count"], 16)
            self.assertEqual(metrics["state_accuracy"], 1.0)
            self.assertEqual(metrics["issue_accuracy"], 1.0)

    def test_replay_policy_review_and_quality_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = self._run_json(root, "causal-beta-frontier-replay")
            policy = self._run_json(root, "causal-beta-frontier-policy")
            review = self._run_json(root, "causal-beta-frontier-review")
            quality = self._run_json(root, "causal-beta-frontier-quality-gate")
            self.assertTrue(replay["deterministic"])
            self.assertEqual(replay["row_count"], 16)
            self.assertEqual(len(policy["decisions"]), 16)
            self.assertEqual(review["retained_count"], 4)
            self.assertEqual(review["review_count"], 5)
            self.assertEqual(review["blocked_count"], 8)
            self.assertTrue(quality["accepted"])
            self.assertEqual(quality["failed_count"], 0)

    def test_runtime_release_depth_integrity_and_matrix_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = self._run_json(root, "causal-beta-frontier-runtime")
            release = self._run_json(root, "causal-beta-frontier-release")
            depth = self._run_json(root, "causal-beta-frontier-depth-audit")
            integrity = self._run_json(root, "causal-beta-frontier-integrity")
            scenarios = self._run_json(root, "causal-beta-frontier-scenarios")
            validation = self._run_json(root, "causal-beta-frontier-validation-matrix")
            operational = self._run_json(root, "causal-beta-frontier-operational")
            boundary = self._run_json(root, "causal-beta-frontier-boundary")
            assurance = self._run_json(root, "causal-beta-frontier-assurance")
            runbook = self._run_json(root, "causal-beta-frontier-runbook")
            summary = self._run_json(root, "causal-beta-frontier-summary")
            self.assertTrue(runtime["accepted"])
            self.assertEqual(runtime["stage_count"], 27)
            self.assertTrue(release["accepted"])
            self.assertEqual(release["state"], "ready")
            self.assertTrue(depth["accepted"])
            self.assertEqual(depth["failed_check_ids"], [])
            self.assertTrue(integrity["accepted"])
            self.assertEqual(len(scenarios["scenarios"]), 16)
            self.assertEqual(validation["cell_count"], 16)
            self.assertEqual(operational["allowed_count"], 4)
            self.assertTrue(boundary["accepted"])
            self.assertTrue(assurance["accepted"])
            self.assertTrue(runbook["accepted"])
            self.assertEqual(len(runbook["steps"]), 12)
            self.assertEqual(summary["retained_count"], 4)

    def test_review_exports_preserve_rows_and_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "review.csv"
            md_path = root / "review.md"
            json_path = root / "exports.json"
            self.assertEqual(main(["export-causal-beta-frontier-review-csv", "--output", str(csv_path)]), 0)
            self.assertEqual(main(["export-causal-beta-frontier-review-markdown", "--output", str(md_path)]), 0)
            self.assertEqual(main(["export-causal-beta-frontier-json", "--output", str(json_path)]), 0)
            csv_text = csv_path.read_text(encoding="utf-8")
            markdown = md_path.read_text(encoding="utf-8")
            exports = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertTrue(csv_text.startswith("record_id,operation"))
            self.assertEqual(len(csv_text.splitlines()), 17)
            self.assertIn("D11-C08-C2", csv_text)
            self.assertIn("| record_id |", markdown)
            self.assertIn("D11-C05-P", markdown)
            self.assertTrue(exports["accepted"])
            self.assertEqual(exports["export_count"], 6)

    def test_nondefault_fixture_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unused.json"
            path.write_text("{}", encoding="utf-8")
            with redirect_stderr(StringIO()):
                self.assertEqual(main(["causal-beta-frontier-runtime", str(path)]), 2)

    def test_help_lists_the_full_beta_surface(self) -> None:
        with self.assertRaises(SystemExit) as raised, redirect_stdout(StringIO()):
            main(["--help"])
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
