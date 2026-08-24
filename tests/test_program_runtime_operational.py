"""Deep verification for the architecture-program operational handoff trace."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.program_runtime_bundle import build_program_release
from glio_noncode.program_runtime_execution import run_program_runtime
from glio_noncode.program_runtime_operational import (
    PROGRAM_OPERATIONAL_ARTIFACT_COUNT,
    PROGRAM_OPERATIONAL_CHECK_COUNT,
    PROGRAM_OPERATIONAL_STAGE_COUNT,
    build_program_operational_trace,
    verify_program_operational_trace,
)


class ProgramRuntimeOperationalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_program_runtime()
        cls.release = build_program_release(cls.runtime)
        cls.trace = build_program_operational_trace(cls.runtime, cls.release)

    def test_trace_closes_program_and_release_denominators(self) -> None:
        self.assertTrue(self.trace.accepted)
        self.assertEqual(len(self.trace.stages), PROGRAM_OPERATIONAL_STAGE_COUNT)
        self.assertEqual(len(self.trace.artifacts), PROGRAM_OPERATIONAL_ARTIFACT_COUNT)
        self.assertEqual(len(self.trace.checks), PROGRAM_OPERATIONAL_CHECK_COUNT)
        self.assertEqual(self.trace.passed_checks, PROGRAM_OPERATIONAL_CHECK_COUNT)
        self.assertEqual(self.trace.failed_checks, 0)
        self.assertEqual(self.trace.failed_check_ids, ())
        self.assertEqual(verify_program_operational_trace(self.trace), ())

    def test_stage_receipts_are_ordered_budgeted_and_conserved(self) -> None:
        self.assertEqual(
            tuple(item.sequence for item in self.trace.stages),
            tuple(range(1, PROGRAM_OPERATIONAL_STAGE_COUNT + 1)),
        )
        self.assertTrue(all(item.work_units > 0 for item in self.trace.stages))
        self.assertTrue(all(item.within_budget for item in self.trace.stages))
        self.assertEqual(
            self.trace.counter_map["total_stage_work_units"],
            sum(item.work_units for item in self.trace.stages),
        )
        self.assertEqual(
            self.trace.counter_map["total_stage_budget_units"],
            sum(item.budget_units for item in self.trace.stages),
        )
        self.assertGreater(self.trace.counter_map["stage_utilization_percent"], 0)
        self.assertLessEqual(self.trace.counter_map["stage_utilization_percent"], 100)

    def test_artifact_receipts_are_addressed_and_budgeted(self) -> None:
        self.assertEqual(
            {item.filename for item in self.trace.artifacts},
            {item.filename for item in self.release.artifacts},
        )
        self.assertTrue(all(item.byte_count > 0 for item in self.trace.artifacts))
        self.assertTrue(all(item.line_count > 0 for item in self.trace.artifacts))
        self.assertTrue(all(item.within_budget for item in self.trace.artifacts))
        self.assertEqual(
            self.trace.counter_map["total_artifact_bytes"],
            sum(item.byte_count for item in self.trace.artifacts),
        )
        self.assertEqual(
            self.trace.counter_map["total_artifact_lines"],
            sum(item.line_count for item in self.trace.artifacts),
        )
        self.assertGreater(self.trace.counter_map["artifact_utilization_percent"], 0)

    def test_mutated_stage_or_artifact_is_rejected(self) -> None:
        edited_stage = replace(self.trace.stages[0], work_units=self.trace.stages[0].work_units + 1)
        edited_stage_trace = replace(
            self.trace,
            stages=(edited_stage,) + self.trace.stages[1:],
        )
        stage_failures = verify_program_operational_trace(edited_stage_trace)
        self.assertIn("stage-address:catalog-loaded", stage_failures)
        self.assertIn("operational-address-integrity", stage_failures)

        edited_artifact = replace(
            self.trace.artifacts[0], byte_count=self.trace.artifacts[0].byte_count + 1
        )
        edited_artifact_trace = replace(
            self.trace,
            artifacts=(edited_artifact,) + self.trace.artifacts[1:],
        )
        artifact_failures = verify_program_operational_trace(edited_artifact_trace)
        self.assertIn("artifact-address:program-runtime.json", artifact_failures)
        self.assertIn("operational-address-integrity", artifact_failures)

    def test_checked_in_closure_matches_trace_denominators(self) -> None:
        path = Path(__file__).parents[1] / "data" / "architecture-program-operational-closure.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["stage_count"], PROGRAM_OPERATIONAL_STAGE_COUNT)
        self.assertEqual(payload["artifact_count"], PROGRAM_OPERATIONAL_ARTIFACT_COUNT)
        self.assertEqual(payload["check_count"], PROGRAM_OPERATIONAL_CHECK_COUNT)
        self.assertEqual(payload["failed_check_ids"], [])
        self.assertEqual(payload["passed_checks"], PROGRAM_OPERATIONAL_CHECK_COUNT)
        self.assertTrue(payload["operational"]["accepted"])
        self.assertTrue(payload["release"]["accepted"])
        self.assertGreater(len(payload["artifact_payload_lines"]["program-runtime.json"]), 2000)
        self.assertEqual(
            payload["counters"]["program_check_count"],
            len(self.runtime.report.checks),
        )

    def test_operational_cli_writes_json_projection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-operational-") as directory:
            output = Path(directory) / "operational.json"
            status = main(["architecture-program-operational", "--output", str(output)])
            self.assertEqual(status, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["check_count"], PROGRAM_OPERATIONAL_CHECK_COUNT)
            self.assertEqual(payload["counters"]["domain_count"], 16)

            closure_output = Path(directory) / "closure.json"
            closure_status = main(
                [
                    "architecture-program-operational",
                    "--closure",
                    "--output",
                    str(closure_output),
                ]
            )
            self.assertEqual(closure_status, 0)
            closure = json.loads(closure_output.read_text(encoding="utf-8"))
            self.assertTrue(closure["operational"]["accepted"])
            self.assertEqual(
                len(closure["artifact_payload_lines"]),
                PROGRAM_OPERATIONAL_ARTIFACT_COUNT,
            )


if __name__ == "__main__":
    unittest.main()
