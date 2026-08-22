from __future__ import annotations

import json
import subprocess
import sys
import unittest

from glio_noncode.sequence_effect_frontier_cli import SEQUENCE_EFFECT_FRONTIER_COMMANDS


class SequenceEffectFrontierCliTests(unittest.TestCase):
    def run_cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "glio_noncode", command, *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_command_catalog_is_complete(self) -> None:
        self.assertEqual(len(SEQUENCE_EFFECT_FRONTIER_COMMANDS), 25)
        self.assertEqual(len(set(SEQUENCE_EFFECT_FRONTIER_COMMANDS)), 25)

    def test_audit_evaluate_and_quality_commands(self) -> None:
        for command in (
            "sequence-effect-data-audit",
            "sequence-effect-evaluate",
            "sequence-effect-quality-gate",
        ):
            result = self.run_cli(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["accepted"])

    def test_pipeline_and_review_commands(self) -> None:
        pipeline = self.run_cli("sequence-effect-pipeline", "--run-id", "sequence-effect-cli-test")
        self.assertEqual(pipeline.returncode, 0, pipeline.stderr)
        self.assertTrue(json.loads(pipeline.stdout)["accepted"])
        review = self.run_cli("export-sequence-effect-review-csv")
        self.assertEqual(review.returncode, 0, review.stderr)
        self.assertTrue(review.stdout.startswith("record_id,operation,role,state"))
        self.assertEqual(len(review.stdout.splitlines()), 17)

    def test_operations_emit_addressed_json(self) -> None:
        for command in (
            "sequence-effect-contracts",
            "sequence-effect-schema",
            "sequence-effect-lineage",
            "sequence-effect-adapters",
            "sequence-effect-thresholds",
            "sequence-effect-validation",
            "sequence-effect-runbook",
        ):
            result = self.run_cli(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(
                payload.get("content_address") or payload.get("contracts") or payload.get("schemas")
            )


if __name__ == "__main__":
    unittest.main()
