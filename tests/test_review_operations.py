"""Deep tests for reproducible review SLA and workload projections."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.review_operations import (
    REVIEW_OPERATIONS_MAX_DUE_SOON_HOURS,
    REVIEW_OPERATIONS_MAX_LIMIT,
    build_review_operations_closure,
    build_review_operations_report,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest

AS_OF = "2026-09-01T12:00:00Z"


class ReviewOperationsTests(unittest.TestCase):
    def _three_runs(self, directory: str) -> tuple[CaseRuntime, tuple[str, str, str]]:
        runtime = CaseRuntime(directory)
        runs = tuple(
            runtime.evaluate(
                replace(
                    fixture_manifest(),
                    case_id=f"case-operations-{index}",
                    requested_by=f"researcher-{index}",
                )
            ).run_id
            for index in range(1, 4)
        )
        return runtime, runs

    def _assign(
        self,
        runtime: CaseRuntime,
        run_id: str,
        assignment_id: str,
        reviewer: str,
        due_at: str,
        queue_id: str = "operations-queue",
    ) -> None:
        result = runtime.assign_review(
            run_id,
            assignment_id=assignment_id,
            reviewer=reviewer,
            queue_id=queue_id,
            due_at=due_at,
            note="Operations projection fixture.",
        )
        self.assertTrue(result["accepted"])

    def test_as_of_classifies_due_states_and_workloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, runs = self._three_runs(directory)
            self._assign(runtime, runs[0], "ops-assignment-1", "reviewer-a", "2026-08-20T12:00:00Z")
            self._assign(runtime, runs[1], "ops-assignment-2", "reviewer-a", "2026-09-02T12:00:00Z")
            self._assign(runtime, runs[2], "ops-assignment-3", "reviewer-b", "2026-12-01T12:00:00Z")

            report = build_review_operations_report(runtime, scope="open", as_of=AS_OF)
            self.assertTrue(report.accepted)
            self.assertEqual(report.total_count, 3)
            self.assertEqual(report.counts["overdue"], 1)
            self.assertEqual(report.counts["due_soon"], 1)
            self.assertEqual(report.counts["scheduled"], 1)
            self.assertEqual(report.rows[0].run_id, runs[0])
            self.assertEqual(report.rows[0].due_state, "overdue")
            self.assertEqual(report.rows[0].operational_action, "escalate_overdue")
            self.assertGreater(report.rows[0].age_seconds, 0)
            self.assertLess(report.rows[1].due_in_seconds, 48 * 60 * 60)
            reviewer_a = next(item for item in report.workloads if item.reviewer == "reviewer-a")
            self.assertEqual(reviewer_a.total_count, 2)
            self.assertEqual(reviewer_a.overdue_count, 1)
            self.assertEqual(reviewer_a.due_soon_count, 1)
            self.assertEqual(reviewer_a.open_count, 2)
            reviewer_b = next(item for item in report.workloads if item.reviewer == "reviewer-b")
            self.assertEqual(reviewer_b.total_count, 1)
            self.assertEqual(reviewer_b.overdue_count, 0)

    def test_completed_work_is_not_reported_as_overdue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, runs = self._three_runs(directory)
            self._assign(runtime, runs[0], "ops-completed-assignment", "reviewer-a", "2026-08-20T12:00:00Z")
            stored = runtime.get_dossier(runtime.get_run(runs[0])["dossier_address"])
            runtime.review_run(
                runs[0],
                ReviewDecision(
                    review_id="ops-completed-review",
                    case_id=stored["case_id"],
                    reviewer="reviewer-a",
                    state=ReviewState.ACCEPTED,
                    reviewed_hypothesis_ids=(stored["hypotheses"][0]["hypothesis_id"],),
                    rationale="The completed review remains research-only.",
                    checked_claim_ids=tuple(item["evidence_id"] for item in stored["evidence"]),
                ),
            )
            report = build_review_operations_report(runtime, scope="all", as_of=AS_OF)
            completed = next(item for item in report.rows if item.run_id == runs[0])
            self.assertEqual(completed.queue_state, "completed")
            self.assertEqual(completed.due_state, "completed")
            self.assertEqual(completed.operational_action, "none")
            self.assertIsNone(completed.due_in_seconds)
            self.assertEqual(report.counts["completed"], 1)
            self.assertEqual(report.counts["overdue"], 0)
            workload = next(item for item in report.workloads if item.reviewer == "reviewer-a")
            self.assertEqual(workload.completed_count, 1)
            self.assertEqual(workload.open_count, 0)

    def test_invalid_due_time_fails_closed_and_is_filterable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, runs = self._three_runs(directory)
            self._assign(runtime, runs[0], "ops-invalid-assignment", "reviewer-a", "not-an-instant")
            report = build_review_operations_report(runtime, scope="open", as_of=AS_OF)
            invalid = next(item for item in report.rows if item.run_id == runs[0])
            self.assertEqual(invalid.due_state, "invalid")
            self.assertEqual(invalid.operational_action, "repair_assignment")
            self.assertFalse(invalid.accepted)
            self.assertFalse(report.accepted)
            filtered = build_review_operations_report(runtime, scope="open", due_state="invalid", as_of=AS_OF)
            self.assertEqual(filtered.total_count, 1)
            self.assertEqual(filtered.rows[0].run_id, runs[0])

    def test_reports_are_reproducible_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, runs = self._three_runs(directory)
            for index, run_id in enumerate(runs, start=1):
                self._assign(
                    runtime,
                    run_id,
                    f"ops-reproducible-{index}",
                    "reviewer-reproducible",
                    f"2026-10-0{index}T12:00:00Z",
                )
            first = build_review_operations_report(runtime, scope="all", as_of=AS_OF, limit=2)
            second = build_review_operations_report(runtime, scope="all", as_of=AS_OF, limit=2)
            self.assertTrue(first.accepted)
            self.assertEqual(first.content_address, second.content_address)
            self.assertEqual(first.total_count, 3)
            self.assertTrue(first.has_more)
            self.assertEqual(len(first.rows), 2)
            self.assertEqual(first.rows[0].to_dict(), second.rows[0].to_dict())
            closure = build_review_operations_closure(runtime, as_of=AS_OF)
            self.assertTrue(closure["accepted"])
            self.assertEqual(closure["report"]["total_count"], 3)
            self.assertFalse(closure["report"]["has_more"])
            self.assertTrue(closure["content_address"].startswith("review-operations-closure:"))
            rendered = json.dumps(closure, sort_keys=True).lower()
            self.assertNotIn("generated_by", rendered)
            self.assertNotIn("assistant_name", rendered)
            self.assertNotIn("programming_language", rendered)

    def test_invalid_bounds_and_clock_values_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            with self.assertRaises(ValidationError):
                build_review_operations_report(runtime, as_of="not-an-instant")
            with self.assertRaises(ValidationError):
                build_review_operations_report(runtime, due_soon_hours=0)
            with self.assertRaises(ValidationError):
                build_review_operations_report(runtime, due_soon_hours=REVIEW_OPERATIONS_MAX_DUE_SOON_HOURS + 1)
            with self.assertRaises(ValidationError):
                build_review_operations_report(runtime, limit=REVIEW_OPERATIONS_MAX_LIMIT + 1)
            with self.assertRaises(ValidationError):
                build_review_operations_report(runtime, due_state="not-a-state")

    def test_cli_and_http_expose_as_of_operations_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            assignment_path = Path(directory) / "assignment.json"
            assignment_result_path = Path(directory) / "assignment-result.json"
            operations_path = Path(directory) / "operations.json"
            assignment_path.write_text(
                json.dumps(
                    {
                        "assignment_id": "ops-cli-assignment",
                        "reviewer": "reviewer-cli",
                        "queue_id": "cli-operations",
                        "due_at": "2026-09-02T12:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "review-assign",
                        dossier.run_id,
                        str(assignment_path),
                        "--data-root",
                        directory,
                        "--output",
                        str(assignment_result_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "review-operations",
                        "--data-root",
                        directory,
                        "--as-of",
                        AS_OF,
                        "--due-state",
                        "due_soon",
                        "--output",
                        str(operations_path),
                    ]
                ),
                0,
            )
            operations = json.loads(operations_path.read_text(encoding="utf-8"))
            self.assertTrue(operations["accepted"])
            self.assertEqual(operations["total_count"], 1)
            self.assertEqual(operations["rows"][0]["operational_action"], "confirm_capacity")

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", f"/v1/review-operations?scope=all&as_of={AS_OF}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["total_count"], 1)
                self.assertEqual(payload["workloads"][0]["reviewer"], "reviewer-cli")
                connection.request("GET", f"/v1/review-operations/closure?as_of={AS_OF}")
                closure_response = connection.getresponse()
                self.assertEqual(closure_response.status, 200)
                self.assertEqual(json.loads(closure_response.read())["report"]["total_count"], 1)
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
