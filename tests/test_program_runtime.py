"""Deep verification for the sixteen-domain architecture program runtime."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.program_runtime import (
    PROGRAM_CHECKS_PER_DOMAIN,
    PROGRAM_DOMAIN_COUNT,
    architecture_program_domain_matrix,
    architecture_program_percent,
    query_architecture_program,
)
from glio_noncode.program_runtime_contracts import ProgramRuntimeState
from glio_noncode.program_runtime_execution import (
    PROGRAM_RUNTIME_STAGE_COUNT,
    run_program_runtime,
)
from glio_noncode.program_runtime_exports import (
    architecture_program_checks_csv,
    architecture_program_domains_csv,
    architecture_program_receipts_csv,
    architecture_program_report_json,
    architecture_program_report_markdown,
    architecture_program_summary_json,
)
from glio_noncode.program_runtime_quality import (
    PROGRAM_QUALITY_CHECK_COUNT,
    run_program_runtime_quality_gate,
)
from glio_noncode.program_runtime_replay import (
    replay_architecture_program,
    run_program_runtime_failure_injections,
)


class ProgramRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_program_runtime()
        cls.report = cls.runtime.report

    def test_all_sixteen_domains_execute_and_reconcile(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.state, ProgramRuntimeState.ACCEPTED)
        self.assertEqual(len(self.report.specs), PROGRAM_DOMAIN_COUNT)
        self.assertEqual(len(self.report.receipts), PROGRAM_DOMAIN_COUNT)
        self.assertEqual(len(self.report.checks), PROGRAM_DOMAIN_COUNT * PROGRAM_CHECKS_PER_DOMAIN + 12)
        self.assertEqual(self.report.passed_checks, len(self.report.checks))
        self.assertEqual(self.report.failed_checks, 0)
        self.assertEqual(architecture_program_percent(self.report), 100.0)

    def test_domain_receipts_are_deep_and_public(self) -> None:
        self.assertTrue(all(item.accepted for item in self.report.receipts))
        self.assertTrue(all(item.stage_count >= 20 for item in self.report.receipts))
        self.assertTrue(all(item.evaluation_check_count > 0 for item in self.report.receipts))
        self.assertTrue(all(item.artifact_count > 0 for item in self.report.receipts))
        self.assertTrue(all(not item.issue_codes for item in self.report.receipts))
        self.assertTrue(all(":" in item.fixture_address for item in self.report.receipts))
        self.assertTrue(all(":" in item.runtime_address for item in self.report.receipts))

    def test_d08_public_boundary_is_closed(self) -> None:
        d08 = next(item for item in self.report.receipts if item.domain_id == "D08")
        self.assertEqual(d08.issue_codes, ())
        self.assertTrue(all("private_projection_key" not in item.issue_codes for item in self.report.receipts))

    def test_quality_and_ordered_stage_denominators(self) -> None:
        quality = run_program_runtime_quality_gate(self.report)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), PROGRAM_QUALITY_CHECK_COUNT)
        self.assertEqual(quality.passed_checks, PROGRAM_QUALITY_CHECK_COUNT)
        self.assertEqual(len(self.runtime.stages), PROGRAM_RUNTIME_STAGE_COUNT)
        self.assertEqual([item.ordinal for item in self.runtime.stages], list(range(1, 13)))
        self.assertEqual([item.stage_id for item in self.runtime.stages][-1], "runtime-finalized")
        self.assertTrue(all(item.state is ProgramRuntimeState.ACCEPTED for item in self.runtime.stages))

    def test_matrix_and_queries_are_operational(self) -> None:
        matrix = architecture_program_domain_matrix(self.report)
        self.assertEqual(len(matrix), PROGRAM_DOMAIN_COUNT)
        self.assertEqual(len(query_architecture_program(self.report, domain_id="D08")), 1)
        self.assertEqual(len(query_architecture_program(self.report, accepted_only=True)), 16)
        self.assertEqual(len(query_architecture_program(self.report, text="cell state")), 1)

    def test_exports_retain_complete_denominators(self) -> None:
        report_payload = json.loads(architecture_program_report_json(self.report))
        summary = json.loads(architecture_program_summary_json(self.report))
        self.assertEqual(report_payload["state"], "accepted")
        self.assertEqual(summary["certification_percent"], 100.0)
        self.assertEqual(len(architecture_program_receipts_csv(self.report).splitlines()), 17)
        self.assertEqual(len(architecture_program_domains_csv(self.report).splitlines()), 17)
        self.assertEqual(len(architecture_program_checks_csv(self.report).splitlines()), 173)
        self.assertIn("# Architecture program runtime", architecture_program_report_markdown(self.report))

    def test_replay_and_failure_controls(self) -> None:
        replay = replay_architecture_program()
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.first_report_address, replay.second_report_address)
        self.assertEqual(replay.first_runtime_address, replay.second_runtime_address)
        failures = run_program_runtime_failure_injections()
        self.assertTrue(failures.accepted)
        self.assertEqual(len(failures.probes), 2)
        self.assertTrue(all(item.passed for item in failures.probes))
        self.assertTrue(all(item.observed_state is ProgramRuntimeState.REVIEW for item in failures.probes))

    def test_checked_in_closure_matches_program_denominators(self) -> None:
        path = Path(__file__).parents[1] / "data" / "architecture-program-runtime-closure.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["runtime"]["state"], "accepted")
        self.assertEqual(payload["runtime"]["stage_count"], PROGRAM_RUNTIME_STAGE_COUNT)
        self.assertEqual(payload["report"]["domain_count"], PROGRAM_DOMAIN_COUNT)
        self.assertEqual(payload["report"]["check_count"], 172)
        self.assertEqual(payload["quality"]["passed_checks"], PROGRAM_QUALITY_CHECK_COUNT)
        self.assertTrue(payload["failure_controls"]["accepted"])


if __name__ == "__main__":
    unittest.main()
