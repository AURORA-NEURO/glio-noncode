"""Deep tests for durable review assignment and deterministic queue projections."""

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
from glio_noncode.review_queue import (
    REVIEW_QUEUE_MAX_LIMIT,
    build_review_queue_closure,
    build_review_queue_page,
)
from glio_noncode.run_catalog import inspect_run
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class ReviewQueueTests(unittest.TestCase):
    def _runtime_with_runs(self, directory: str) -> tuple[CaseRuntime, str, str]:
        runtime = CaseRuntime(directory)
        first = runtime.evaluate(fixture_manifest())
        second = runtime.evaluate(
            replace(
                fixture_manifest(),
                case_id="case-demo-002",
                requested_by="researcher-2",
            )
        )
        return runtime, first.run_id, second.run_id

    def _accept(self, runtime: CaseRuntime, run_id: str, review_id: str) -> None:
        dossier = runtime.get_dossier(runtime.get_run(run_id)["dossier_address"])
        runtime.review_run(
            run_id,
            ReviewDecision(
                review_id=review_id,
                case_id=dossier["case_id"],
                reviewer="scientific-reviewer",
                state=ReviewState.ACCEPTED,
                reviewed_hypothesis_ids=(dossier["hypotheses"][0]["hypothesis_id"],),
                rationale="The review verifies the bounded research dossier.",
                checked_claim_ids=tuple(item["evidence_id"] for item in dossier["evidence"]),
            ),
        )

    def test_queue_is_priority_ordered_and_filterable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, first_id, second_id = self._runtime_with_runs(directory)
            page = build_review_queue_page(runtime)
            self.assertTrue(page.accepted)
            self.assertEqual(page.total_count, 2)
            self.assertEqual([item.queue_state for item in page.rows], ["unassigned", "unassigned"])
            self.assertTrue(page.rows[0].priority_score >= page.rows[1].priority_score)
            self.assertTrue(all("review_missing" in item.priority_reasons for item in page.rows))
            self.assertTrue(all("no_active_assignment" in item.priority_reasons for item in page.rows))
            self.assertEqual(
                {item.run_id for item in build_review_queue_page(runtime, scope="unassigned").rows},
                {first_id, second_id},
            )
            filtered = build_review_queue_page(runtime, case_id="case-demo-002")
            self.assertEqual(filtered.total_count, 1)
            self.assertEqual(filtered.rows[0].case_id, "case-demo-002")
            by_text = build_review_queue_page(runtime, text="review_missing")
            self.assertEqual(by_text.total_count, 2)

    def test_assignment_is_append_only_and_visible_in_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            before = inspect_run(runtime, dossier.run_id)
            before_snapshot_count = len(runtime.get_run(dossier.run_id).get("dossier_history", ()))
            result = runtime.assign_review(
                dossier.run_id,
                assignment_id="assignment-001",
                reviewer="reviewer-alpha",
                queue_id="neuro-oncology",
                due_at="2026-09-01T12:00:00+00:00",
                note="Prioritize the regulatory evidence branch.",
            )
            self.assertTrue(result["accepted"])
            self.assertEqual(result["assignment"]["reviewer"], "reviewer-alpha")
            self.assertTrue(result["assignment"]["content_address"].startswith("review-assignment:"))
            after = inspect_run(runtime, dossier.run_id)
            self.assertTrue(after.accepted)
            self.assertEqual(len(after.event_record["events"]), len(before.event_record["events"]) + 1)
            self.assertEqual(after.event_record["events"][-1]["event_type"], "review_assigned")
            self.assertGreater(len(runtime.get_run(dossier.run_id).get("dossier_history", ())), before_snapshot_count)
            page = build_review_queue_page(runtime, scope="assigned", reviewer="reviewer-alpha", queue_id="neuro-oncology")
            self.assertTrue(page.accepted)
            self.assertEqual(page.total_count, 1)
            self.assertEqual(page.rows[0].assignment.assignment_id, "assignment-001")
            self.assertEqual(page.rows[0].queue_state, "assigned")

            with self.assertRaises(ValidationError):
                runtime.assign_review(
                    dossier.run_id,
                    assignment_id="assignment-001",
                    reviewer="reviewer-beta",
                )

    def test_completed_reviews_leave_open_queue_and_remain_in_all_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, first_id, second_id = self._runtime_with_runs(directory)
            self._accept(runtime, first_id, "review-accepted-001")
            open_page = build_review_queue_page(runtime, scope="open")
            self.assertTrue(open_page.accepted)
            self.assertEqual(open_page.total_count, 1)
            self.assertEqual(open_page.rows[0].run_id, second_id)
            all_page = build_review_queue_page(runtime, scope="all")
            completed = next(item for item in all_page.rows if item.run_id == first_id)
            self.assertEqual(completed.queue_state, "completed")
            self.assertEqual(completed.review_state, ReviewState.ACCEPTED.value)
            self.assertEqual(completed.priority_score, 0)
            self.assertIn("review_completed", completed.priority_reasons)
            with self.assertRaises(ValidationError):
                runtime.assign_review(
                    first_id,
                    assignment_id="assignment-after-review",
                    reviewer="reviewer-alpha",
                )

    def test_closure_has_operational_counters_and_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, _ = self._runtime_with_runs(directory)
            closure = build_review_queue_closure(runtime)
            self.assertTrue(closure["accepted"])
            self.assertEqual(closure["queue_version"], "review-queue-v1")
            self.assertEqual(closure["summary"]["total_count"], 2)
            self.assertEqual(closure["summary"]["queue_state_counts"], {"unassigned": 2})
            self.assertEqual(closure["summary"]["blocked_count"], 0)
            self.assertTrue(closure["content_address"].startswith("review-queue-closure:"))
            rendered = json.dumps(closure, sort_keys=True).lower()
            self.assertNotIn("generated_by", rendered)
            self.assertNotIn("assistant_name", rendered)
            self.assertNotIn("programming_language", rendered)

    def test_queue_rejects_unbounded_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            with self.assertRaises(ValueError):
                build_review_queue_page(runtime, limit=REVIEW_QUEUE_MAX_LIMIT + 1)
            with self.assertRaises(ValueError):
                build_review_queue_page(runtime, offset=-1)
            with self.assertRaises(ValueError):
                build_review_queue_page(runtime, scope="invalid")

    def test_cli_queue_and_assignment_commands_write_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            assignment_path = Path(directory) / "assignment.json"
            assignment_result_path = Path(directory) / "assignment-result.json"
            queue_path = Path(directory) / "queue.json"
            closure_path = Path(directory) / "closure.json"
            assignment_path.write_text(
                json.dumps(
                    {
                        "assignment_id": "assignment-cli-001",
                        "reviewer": "reviewer-cli",
                        "queue_id": "cli-queue",
                        "due_at": "2026-09-02T12:00:00+00:00",
                        "note": "CLI assignment",
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
                        "review-queue",
                        "--data-root",
                        directory,
                        "--scope",
                        "assigned",
                        "--reviewer",
                        "reviewer-cli",
                        "--output",
                        str(queue_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "review-queue",
                        "--data-root",
                        directory,
                        "--closure",
                        "--output",
                        str(closure_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(assignment_result_path.read_text(encoding="utf-8"))["accepted"])
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertTrue(queue["accepted"])
            self.assertEqual(queue["rows"][0]["assignment"]["queue_id"], "cli-queue")
            self.assertTrue(json.loads(closure_path.read_text(encoding="utf-8"))["accepted"])

    def test_http_queue_and_assignment_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "POST",
                    "/v1/evaluate",
                    body=json.dumps(fixture_manifest().to_dict()).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                evaluated = connection.getresponse()
                self.assertEqual(evaluated.status, 200)
                run_id = json.loads(evaluated.read())["run_id"]
                assignment = json.dumps(
                    {
                        "assignment_id": "assignment-http-001",
                        "reviewer": "reviewer-http",
                        "queue_id": "http-queue",
                    }
                ).encode("utf-8")
                connection.request(
                    "POST",
                    f"/v1/runs/{run_id}/assignment",
                    body=assignment,
                    headers={"Content-Type": "application/json"},
                )
                assigned = connection.getresponse()
                self.assertEqual(assigned.status, 200)
                self.assertTrue(json.loads(assigned.read())["accepted"])
                connection.request("GET", "/v1/review-queue?scope=assigned&reviewer=reviewer-http")
                queue_response = connection.getresponse()
                self.assertEqual(queue_response.status, 200)
                queue = json.loads(queue_response.read())
                self.assertTrue(queue["accepted"])
                self.assertEqual(queue["total_count"], 1)
                self.assertEqual(queue["rows"][0]["run_id"], run_id)
                connection.request("GET", "/v1/review-queue/closure")
                closure_response = connection.getresponse()
                self.assertEqual(closure_response.status, 200)
                self.assertEqual(json.loads(closure_response.read())["summary"]["total_count"], 1)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
