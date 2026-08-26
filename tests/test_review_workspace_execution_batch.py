from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_execution import (
    ReviewPlanExecutionEventKind,
    ReviewPlanExecutionStore,
    build_review_plan_execution_event,
    replay_review_workspace_plan_execution,
)
from glio_noncode.review_workspace_execution_batch import (
    REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS,
    ReviewWorkspaceExecutionBatchRequest,
    append_review_workspace_plan_execution_batch,
    render_review_workspace_execution_batch_markdown,
    review_workspace_execution_batch_capabilities,
    review_workspace_execution_batch_csv,
    review_workspace_execution_batch_export_payloads,
    review_workspace_execution_batch_from_mapping,
    review_workspace_execution_batch_json,
    review_workspace_execution_batch_schema,
)
from glio_noncode.review_workspace_execution_simulation import (
    ReviewWorkspaceExecutionSimulationProposal,
)
from glio_noncode.review_workspace_plan import build_review_workspace_plan
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash

from .helpers import fixture_manifest


class ReviewWorkspaceExecutionBatchTests(unittest.TestCase):
    def _context(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        workspace = build_persisted_review_workspace(runtime, dossier.run_id)
        return runtime, dossier, build_review_workspace_plan(workspace)

    @staticmethod
    def _event(plan, action, event_id, kind, occurred_at, *, previous=None, checks=(), reason=""):
        return build_review_plan_execution_event(
            plan=plan,
            action_id=action.action_id,
            event_id=event_id,
            kind=kind,
            occurred_at=occurred_at,
            reason=reason,
            check_ids=checks,
            previous_event_address=previous,
        )

    @staticmethod
    def _proposal(action, event_id: str, kind: str, occurred_at: str, **extra):
        body = {
            "action_id": action.action_id,
            "kind": kind,
            "event_id": event_id,
            "occurred_at": occurred_at,
        }
        body.update(extra)
        return body

    def test_store_append_many_validates_before_one_manifest_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            action = plan.actions[0]
            start = self._event(
                plan,
                action,
                "batch-start",
                ReviewPlanExecutionEventKind.START,
                "2026-08-25T12:00:00Z",
            )
            complete = self._event(
                plan,
                action,
                "batch-complete",
                ReviewPlanExecutionEventKind.COMPLETE,
                "2026-08-25T12:01:00Z",
                previous=start.content_address,
                checks=action.required_checks,
            )
            store = ReviewPlanExecutionStore(directory)
            report = store.append_many(plan, (start, complete))
            self.assertTrue(report.accepted)
            self.assertEqual(report.event_count, 2)
            self.assertEqual(tuple(item.event_id for item in store.read_events(plan)), ("batch-start", "batch-complete"))
            invalid_start = self._event(
                plan,
                action,
                "invalid-start",
                ReviewPlanExecutionEventKind.START,
                "2026-08-25T13:00:00Z",
            )
            invalid_complete = self._event(
                plan,
                action,
                "invalid-complete",
                ReviewPlanExecutionEventKind.COMPLETE,
                "2026-08-25T13:01:00Z",
                previous=invalid_start.content_address,
            )
            before = store.read_events(plan)
            with self.assertRaises(ValidationError):
                store.append_many(plan, (invalid_start, invalid_complete))
            self.assertEqual(store.read_events(plan), before)
            with self.assertRaises(ValidationError):
                store.append_many(plan, (invalid_start, invalid_start))
            self.assertEqual(store.read_events(plan), before)

    def test_accepted_batch_commits_simulation_events_and_honors_base_guard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            empty_report = replay_review_workspace_plan_execution(plan)
            action = plan.actions[0]
            proposals = [
                self._proposal(action, "atomic-start", "start", "2026-08-25T12:00:00Z"),
                self._proposal(
                    action,
                    "atomic-complete",
                    "complete",
                    "2026-08-25T12:01:00Z",
                    check_ids=list(action.required_checks),
                ),
            ]
            result = append_review_workspace_plan_execution_batch(
                runtime,
                dossier.run_id,
                proposals,
                expected_execution_address=empty_report.content_address,
                expected_event_count=0,
                expected_last_event_address=None,
            )
            self.assertTrue(result.accepted)
            self.assertTrue(result.committed)
            self.assertTrue(result.no_partial_write)
            self.assertFalse(result.conflict)
            self.assertEqual(result.event_count_before, 0)
            self.assertEqual(result.event_count_after, 2)
            self.assertEqual(result.committed_event_ids, ("atomic-start", "atomic-complete"))
            self.assertEqual(result.final_report.event_count, 2)
            persisted = ReviewPlanExecutionStore(directory).read_events(plan)
            self.assertEqual(tuple(item.event_id for item in persisted), result.committed_event_ids)
            stale = append_review_workspace_plan_execution_batch(
                runtime,
                dossier.run_id,
                [self._proposal(action, "stale-block", "block", "2026-08-25T12:02:00Z", reason="stale")],
                expected_execution_address=empty_report.content_address,
            )
            self.assertFalse(stale.accepted)
            self.assertFalse(stale.committed)
            self.assertTrue(stale.no_partial_write)
            self.assertTrue(stale.conflict)
            self.assertEqual(stale.failure_code, "stale_base")
            self.assertEqual(ReviewPlanExecutionStore(directory).read_events(plan), persisted)

    def test_rejected_batch_is_simulation_receipted_without_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            action = plan.actions[0]
            result = append_review_workspace_plan_execution_batch(
                runtime,
                dossier.run_id,
                [
                    self._proposal(action, "reject-start", "start", "2026-08-25T12:00:00Z"),
                    self._proposal(action, "reject-complete", "complete", "2026-08-25T12:01:00Z"),
                ],
            )
            self.assertFalse(result.accepted)
            self.assertFalse(result.committed)
            self.assertTrue(result.no_partial_write)
            self.assertFalse(result.conflict)
            self.assertEqual(result.failure_code, "required_checks")
            self.assertIsNotNone(result.simulation)
            self.assertEqual(result.simulation.accepted_proposal_count, 1)
            self.assertEqual(result.event_count_before, 0)
            self.assertEqual(result.event_count_after, 0)
            self.assertEqual(result.simulation.final_report.event_count, 1)
            self.assertEqual(ReviewPlanExecutionStore(directory).read_events(plan), ())
            count_mismatch = append_review_workspace_plan_execution_batch(
                runtime,
                dossier.run_id,
                [],
                expected_event_count=1,
            )
            self.assertFalse(count_mismatch.accepted)
            self.assertTrue(count_mismatch.conflict)
            self.assertEqual(count_mismatch.failure_code, "stale_base")

    def test_request_result_exports_and_contracts_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            action = plan.actions[0]
            proposal = ReviewWorkspaceExecutionBatchRequest(
                expected_execution_address=replay_review_workspace_plan_execution(plan).content_address,
                expected_event_count=0,
                expected_last_event_address=None,
                proposals=(
                    ReviewWorkspaceExecutionSimulationProposal.from_mapping(
                        self._proposal(action, "request-start", "start", "2026-08-25T12:00:00Z")
                    ),
                ),
                content_address="pending",
            )
            request_body = {
                "batch_version": proposal._body()["batch_version"],
                "expected_execution_address": proposal.expected_execution_address,
                "expected_event_count": proposal.expected_event_count,
                "expected_last_event_address": proposal.expected_last_event_address,
                "proposals": proposal.proposals,
            }
            request = ReviewWorkspaceExecutionBatchRequest(
                expected_execution_address=proposal.expected_execution_address,
                expected_event_count=0,
                expected_last_event_address=None,
                proposals=proposal.proposals,
                content_address=content_hash(request_body, prefix="review-workspace-execution-batch-request"),
            )
            self.assertEqual(
                ReviewWorkspaceExecutionBatchRequest.from_mapping(request.to_dict()),
                request,
            )
            result = append_review_workspace_plan_execution_batch(
                runtime,
                dossier.run_id,
                [self._proposal(action, "receipt-start", "start", "2026-08-25T12:00:00Z")],
            )
            self.assertEqual(
                review_workspace_execution_batch_from_mapping(result.to_dict()).to_dict(),
                result.to_dict(),
            )
            self.assertEqual(json.loads(review_workspace_execution_batch_json(result)), result.to_dict())
            self.assertIn("request_address", review_workspace_execution_batch_csv(result).splitlines()[0])
            self.assertIn("atomic", render_review_workspace_execution_batch_markdown(result))
            self.assertEqual(
                set(review_workspace_execution_batch_export_payloads(result)),
                {
                    "review-workspace-execution-batch.json",
                    "review-workspace-execution-batch.md",
                    "review-workspace-execution-batch.csv",
                },
            )
            self.assertTrue(review_workspace_execution_batch_capabilities()["optimistic_base_guard"])
            self.assertTrue(review_workspace_execution_batch_schema()["write_policy"]["single_manifest_refresh"])
            tampered = result.to_dict()
            tampered["committed"] = False
            with self.assertRaises(ValidationError):
                review_workspace_execution_batch_from_mapping(tampered)

    def test_cli_and_http_batch_surfaces_append_only_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            action = plan.actions[0]
            proposals_path = Path(directory) / "batch-proposals.json"
            proposals_path.write_text(
                json.dumps([self._proposal(action, "cli-batch-start", "start", "2026-08-25T12:00:00Z")]),
                encoding="utf-8",
            )
            output = Path(directory) / "batch-result.json"
            self.assertEqual(
                main(
                    [
                        "review-workspace-plan-execution-batch",
                        dossier.run_id,
                        "--data-root",
                        directory,
                        "--proposals",
                        str(proposals_path),
                        "--include-simulation",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            cli_result = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(cli_result["committed"])
            self.assertEqual(cli_result["event_count_after"], 1)
            persisted = ReviewPlanExecutionStore(directory).read_events(plan)
            self.assertEqual(tuple(item.event_id for item in persisted), ("cli-batch-start",))
            schema_output = Path(directory) / "batch-schema.json"
            self.assertEqual(
                main(["review-workspace-plan-execution-batch-schema", "--output", str(schema_output)]),
                0,
            )
            self.assertEqual(
                json.loads(schema_output.read_text(encoding="utf-8"))["version"],
                "review-workspace-execution-batch-schema-v1",
            )
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                body = json.dumps(
                    {
                        "proposals": [
                            self._proposal(action, "api-batch-complete", "complete", "2026-08-25T12:01:00Z", check_ids=list(action.required_checks))
                        ],
                        "expected_execution_address": replay_review_workspace_plan_execution(plan, persisted).content_address,
                        "expected_event_count": 1,
                        "expected_last_event_address": persisted[-1].content_address,
                        "include_simulation": True,
                    }
                ).encode("utf-8")
                connection.request(
                    "POST",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution/batch",
                    body=body,
                    headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_result = json.loads(response.read())
                self.assertTrue(api_result["committed"])
                self.assertEqual(api_result["event_count_after"], 2)
                connection.request("GET", "/v1/review-workspace/plan/execution/batch/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    json.loads(response.read())["batch_version"],
                    "review-workspace-execution-batch-v1",
                )
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_batch_bound_is_exposed_and_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            action = plan.actions[0]
            proposals = [
                self._proposal(action, f"bounded-{index}", "start", "2026-08-25T12:00:00Z")
                for index in range(REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS + 1)
            ]
            with self.assertRaises(ValidationError):
                append_review_workspace_plan_execution_batch(runtime, dossier.run_id, proposals)


if __name__ == "__main__":
    unittest.main()
