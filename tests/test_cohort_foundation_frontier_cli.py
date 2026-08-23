"""CLI contract tests for Domain 12 C01-C04."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest


COMMANDS = (
    "cohort-foundation-frontier-data-audit",
    "cohort-foundation-frontier-contracts",
    "cohort-foundation-frontier-schema",
    "cohort-foundation-frontier-evaluate",
    "cohort-foundation-frontier-replay",
    "cohort-foundation-frontier-metrics",
    "cohort-foundation-frontier-lineage",
    "cohort-foundation-frontier-policy",
    "cohort-foundation-frontier-quality-gate",
    "cohort-foundation-frontier-runtime",
    "cohort-foundation-frontier-release",
    "cohort-foundation-frontier-artifacts",
    "cohort-foundation-frontier-depth-audit",
    "cohort-foundation-frontier-diagnostics",
    "cohort-foundation-frontier-scenarios",
    "cohort-foundation-frontier-validation-matrix",
    "cohort-foundation-frontier-operational",
    "cohort-foundation-frontier-boundary",
    "cohort-foundation-frontier-assurance",
    "cohort-foundation-frontier-runbook",
    "cohort-foundation-frontier-report",
    "cohort-foundation-frontier-sources",
    "cohort-foundation-frontier-integrity",
    "cohort-foundation-frontier-control-coverage",
    "cohort-foundation-frontier-traces",
    "cohort-foundation-frontier-invariants",
    "cohort-foundation-frontier-thresholds",
    "cohort-foundation-frontier-observability",
    "cohort-foundation-frontier-accessibility",
    "cohort-foundation-frontier-performance",
    "cohort-foundation-frontier-schema-migrations",
    "cohort-foundation-frontier-failure-injections",
    "cohort-foundation-frontier-recovery",
    "cohort-foundation-frontier-package",
    "cohort-foundation-frontier-claim-evidence",
    "cohort-foundation-frontier-audit-log",
    "cohort-foundation-frontier-review-sla",
    "cohort-foundation-frontier-data-dictionary",
    "cohort-foundation-frontier-compatibility",
    "cohort-foundation-frontier-change-control",
    "cohort-foundation-frontier-retention",
    "cohort-foundation-frontier-reproducibility",
    "cohort-foundation-frontier-dataset-manifest",
    "cohort-foundation-frontier-summary",
)


class CohortFoundationFrontierCliTests(unittest.TestCase):
    def run_command(self, command: str) -> str:
        completed = subprocess.run((sys.executable, "-m", "glio_noncode", command), capture_output=True, text=True, check=True)
        return completed.stdout

    def test_all_json_commands_return_valid_payloads(self) -> None:
        for command in COMMANDS:
            with self.subTest(command=command):
                payload = json.loads(self.run_command(command))
                self.assertIsInstance(payload, dict)

    def test_runtime_command_is_accepted_and_ordered(self) -> None:
        payload = json.loads(self.run_command("cohort-foundation-frontier-runtime"))
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["stages"]), 39)
        self.assertEqual([item["ordinal"] for item in payload["stages"]], list(range(1, 40)))

    def test_review_exports_have_expected_formats(self) -> None:
        csv_text = self.run_command("export-cohort-foundation-frontier-review-csv")
        markdown = self.run_command("export-cohort-foundation-frontier-review-markdown")
        json_text = self.run_command("export-cohort-foundation-frontier-json")
        self.assertTrue(csv_text.startswith("review_id,record_id,operation"))
        self.assertIn("| Record | Operation |", markdown)
        self.assertTrue(json.loads(json_text)["accepted"])

    def test_transcript_command_returns_ordered_text(self) -> None:
        text = self.run_command("cohort-foundation-frontier-transcript")
        self.assertTrue(text.startswith("01 ACCEPTED"))
        self.assertIn("39 ", text)


if __name__ == "__main__":
    unittest.main()
