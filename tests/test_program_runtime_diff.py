"""Deep tests for baseline-to-candidate architecture program comparisons."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.program_runtime_diff import (
    PROGRAM_RUNTIME_DIFF_CHECK_COUNT,
    PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT,
    PROGRAM_RUNTIME_DIFF_STAGE_COUNT,
    build_program_runtime_control,
    build_program_runtime_diff,
    compare_program_runtimes,
    verify_program_runtime_diff,
)
from glio_noncode.program_runtime_execution import run_program_runtime


class ProgramRuntimeDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = run_program_runtime()
        cls.unchanged = compare_program_runtimes(cls.baseline, run_program_runtime())
        cls.control = compare_program_runtimes(
            cls.baseline,
            build_program_runtime_control("missing-fixture"),
        )

    def test_unchanged_comparison_closes_all_levels(self) -> None:
        self.assertTrue(self.unchanged.accepted)
        self.assertFalse(self.unchanged.changed)
        self.assertTrue(self.unchanged.candidate_accepted)
        self.assertEqual(len(self.unchanged.domains), PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT)
        self.assertEqual(len(self.unchanged.stages), PROGRAM_RUNTIME_DIFF_STAGE_COUNT)
        self.assertEqual(len(self.unchanged.integrity_checks), PROGRAM_RUNTIME_DIFF_CHECK_COUNT)
        self.assertEqual(self.unchanged.passed_checks, PROGRAM_RUNTIME_DIFF_CHECK_COUNT)
        self.assertEqual(self.unchanged.failed_check_ids, ())
        self.assertEqual(verify_program_runtime_diff(self.unchanged), ())
        self.assertEqual(self.unchanged.counter_map["changed_domain_count"], 0)
        self.assertEqual(self.unchanged.counter_map["changed_check_count"], 0)
        self.assertEqual(self.unchanged.counter_map["changed_stage_count"], 0)

    def test_missing_fixture_control_is_a_valid_regression_diff(self) -> None:
        self.assertTrue(self.control.accepted)
        self.assertTrue(self.control.changed)
        self.assertFalse(self.control.candidate_accepted)
        domain = next(item for item in self.control.domains if item.domain_id == "D01")
        self.assertEqual(domain.disposition, "accepted_to_review")
        self.assertIn("fixture_reference_failed", domain.issue_codes_added)
        self.assertGreater(self.control.counter_map["newly_failed_check_count"], 0)
        self.assertIn("regressed", {item.disposition for item in self.control.checks})
        self.assertEqual(verify_program_runtime_diff(self.control), ())

    def test_missing_runtime_control_targets_d16(self) -> None:
        diff = build_program_runtime_diff("missing-runtime")
        domain = next(item for item in diff.domains if item.domain_id == "D16")
        self.assertTrue(diff.accepted)
        self.assertFalse(diff.candidate_accepted)
        self.assertEqual(domain.disposition, "accepted_to_review")
        self.assertIn("runtime_reference_failed", domain.issue_codes_added)
        self.assertEqual(verify_program_runtime_diff(diff), ())

    def test_mutated_change_receipt_is_rejected(self) -> None:
        edited = replace(
            self.unchanged.domains[0],
            stage_delta=self.unchanged.domains[0].stage_delta + 1,
        )
        mutated = replace(self.unchanged, domains=(edited,) + self.unchanged.domains[1:])
        failures = verify_program_runtime_diff(mutated)
        self.assertIn("domain-address:D01", failures)
        self.assertIn("diff-address-integrity", failures)

    def test_checked_in_diff_closure_matches_control(self) -> None:
        path = Path(__file__).parents[1] / "data" / "architecture-program-diff-closure.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["control"], "missing-fixture")
        self.assertTrue(payload["accepted"])
        self.assertTrue(payload["diff"]["accepted"])
        self.assertFalse(payload["diff"]["candidate_accepted"])
        self.assertEqual(payload["diff"]["integrity_check_count"], PROGRAM_RUNTIME_DIFF_CHECK_COUNT)
        self.assertEqual(payload["diff"]["failed_check_ids"], [])
        self.assertEqual(payload["diff"]["domain_count"], PROGRAM_RUNTIME_DIFF_DOMAIN_COUNT)
        self.assertGreater(len(payload["baseline"]["stages"]), 0)
        self.assertGreater(len(payload["candidate"]["stages"]), 0)

    def test_diff_cli_writes_control_projection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-diff-") as directory:
            output = Path(directory) / "diff.json"
            status = main(
                [
                    "architecture-program-diff",
                    "--control",
                    "missing-fixture",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(status, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertFalse(payload["candidate_accepted"])
            self.assertGreater(payload["counters"]["newly_failed_check_count"], 0)


if __name__ == "__main__":
    unittest.main()
