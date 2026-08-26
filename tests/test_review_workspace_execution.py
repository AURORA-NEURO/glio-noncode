from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_execution import (
    ReviewPlanExecutionEventKind,
    ReviewPlanExecutionStatus,
    ReviewPlanExecutionStore,
    ReviewWorkspaceExecutionQuery,
    build_review_plan_execution_event,
    query_review_workspace_execution,
    replay_review_workspace_plan_execution,
    review_plan_execution_event_from_mapping,
)
from glio_noncode.review_workspace_execution_exports import (
    render_review_workspace_execution_markdown,
    review_workspace_execution_export_payloads,
)
from glio_noncode.review_workspace_execution_timeline import (
    ReviewWorkspaceExecutionTimelineQuery,
    query_review_workspace_execution_timeline,
    review_workspace_execution_timeline_capabilities,
    review_workspace_execution_timeline_schema,
)
from glio_noncode.review_workspace_execution_metrics import (
    build_review_workspace_execution_metrics,
    render_review_workspace_execution_metrics_markdown,
    review_workspace_execution_metrics_capabilities,
    review_workspace_execution_metrics_export_payloads,
    review_workspace_execution_metrics_schema,
)
from glio_noncode.review_workspace_plan import build_review_workspace_plan
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {
            nested
            for item in value.values()
            for nested in _keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _keys(item)}
    return set()


class ReviewWorkspaceExecutionTests(unittest.TestCase):
    def _context(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        report = build_persisted_review_workspace(runtime, dossier.run_id)
        return runtime, dossier, build_review_workspace_plan(report)

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

    def test_empty_replay_and_dependency_aware_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            initial = replay_review_workspace_plan_execution(plan)
            self.assertTrue(initial.accepted)
            self.assertEqual(initial.state, ReviewPlanExecutionStatus.OPEN)
            self.assertEqual(initial.next_action_ids, (plan.actions[0].action_id,))

            first = plan.actions[0]
            blocked_action = plan.actions[-1]
            with self.assertRaises(ValidationError):
                replay_review_workspace_plan_execution(
                    plan,
                    [self._event(
                        plan,
                        blocked_action,
                        "evt-too-early",
                        ReviewPlanExecutionEventKind.COMPLETE,
                        "2026-08-25T12:00:00Z",
                        checks=blocked_action.required_checks,
                    )],
                )

            start = self._event(
                plan,
                first,
                "evt-start",
                ReviewPlanExecutionEventKind.START,
                "2026-08-25T12:00:00Z",
            )
            complete = self._event(
                plan,
                first,
                "evt-complete",
                ReviewPlanExecutionEventKind.COMPLETE,
                "2026-08-25T12:01:00Z",
                previous=start.content_address,
                checks=first.required_checks,
            )
            report = replay_review_workspace_plan_execution(plan, (start, complete))
            self.assertTrue(report.accepted)
            self.assertEqual(report.completed_count, 1)
            self.assertEqual(report.in_progress_count, 0)
            self.assertIn(plan.actions[1].action_id, report.next_action_ids)
            self.assertEqual(report.events[1].previous_event_address, start.content_address)

    def test_state_transitions_require_reasons_checks_and_chain_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            action = plan.actions[0]
            block = self._event(
                plan,
                action,
                "evt-block",
                "block",
                "2026-08-25T12:00:00Z",
                reason="source check requires review",
            )
            reopened = self._event(
                plan,
                action,
                "evt-reopen",
                "reopen",
                "2026-08-25T12:01:00Z",
                previous=block.content_address,
                reason="new public check is available",
            )
            report = replay_review_workspace_plan_execution(plan, (block, reopened))
            self.assertTrue(report.accepted)
            self.assertEqual(report.actions[0].status, ReviewPlanExecutionStatus.OPEN)
            with self.assertRaises(ValidationError):
                replay_review_workspace_plan_execution(
                    plan,
                    [self._event(
                        plan,
                        action,
                        "evt-bad-complete",
                        "complete",
                        "2026-08-25T12:02:00Z",
                    )],
                )
            malformed = block.to_dict()
            malformed["previous_event_address"] = "wrong-address"
            with self.assertRaises(ValidationError):
                review_plan_execution_event_from_mapping(malformed)

    def test_append_only_store_reloads_and_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            store = ReviewPlanExecutionStore(directory)
            action = plan.actions[0]
            start = self._event(
                plan,
                action,
                "evt-start",
                "start",
                "2026-08-25T12:00:00Z",
            )
            complete = self._event(
                plan,
                action,
                "evt-complete",
                "complete",
                "2026-08-25T12:01:00Z",
                previous=start.content_address,
                checks=action.required_checks,
            )
            store.append(plan, start)
            report = store.append(plan, complete)
            self.assertEqual(len(store.read_events(plan)), 2)
            self.assertEqual(report.event_count, 2)
            ledger = Path(directory) / "review-plan-execution" / plan.content_address.split(":", 1)[1] / "events.jsonl"
            ledger.write_bytes(ledger.read_bytes().replace(b"evt-start", b"evt-altered"))
            with self.assertRaises(StoreError):
                store.read_events(plan)

    def test_query_exports_and_public_boundary_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            report = replay_review_workspace_plan_execution(plan)
            query = query_review_workspace_execution(
                report,
                ReviewWorkspaceExecutionQuery(status="open", lane="intake", limit=2),
            )
            self.assertTrue(query.accepted)
            self.assertEqual(query, query_review_workspace_execution(report, query.query))
            self.assertEqual(query.total_count, 1)
            payloads = review_workspace_execution_export_payloads(report)
            self.assertEqual(payloads, review_workspace_execution_export_payloads(report))
            self.assertIn("Replay checks", render_review_workspace_execution_markdown(report))
            self.assertNotIn("subject_id", _keys(report.to_dict()))
            self.assertNotIn("agent_id", _keys(report.to_dict()))

    def test_event_timeline_is_sequence_aware_faceted_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            action = plan.actions[0]
            start = self._event(
                plan,
                action,
                "timeline-start",
                ReviewPlanExecutionEventKind.START,
                "2026-08-25T12:00:00Z",
                reason="open public review step",
            )
            complete = self._event(
                plan,
                action,
                "timeline-complete",
                ReviewPlanExecutionEventKind.COMPLETE,
                "2026-08-25T12:01:00Z",
                previous=start.content_address,
                checks=action.required_checks,
                reason="required checks observed",
            )
            report = replay_review_workspace_plan_execution(plan, (start, complete))
            result = query_review_workspace_execution_timeline(
                report,
                ReviewWorkspaceExecutionTimelineQuery(
                    kind="complete",
                    check_id=action.required_checks[0],
                    occurred_from="2026-08-25T12:00:30Z",
                    sequence_start=1,
                    limit=1,
                ),
            )
            self.assertTrue(result.accepted)
            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.rows[0].sequence, 1)
            self.assertEqual(result.rows[0].event.event_id, "timeline-complete")
            self.assertEqual(result.first_sequence, 1)
            self.assertEqual(result.last_sequence, 1)
            self.assertEqual(result.facets["kinds"], {"complete": 1})
            self.assertEqual(result, query_review_workspace_execution_timeline(report, result.query))
            self.assertTrue(review_workspace_execution_timeline_capabilities()["sequence_pagination"])
            self.assertEqual(
                review_workspace_execution_timeline_schema()["ordering"]["field"],
                "sequence",
            )
            with self.assertRaises(ValidationError):
                ReviewWorkspaceExecutionTimelineQuery(
                    occurred_from="2026-08-25T13:00:00Z",
                    occurred_to="2026-08-25T12:00:00Z",
                )

    def test_execution_metrics_measure_timing_checks_lanes_and_critical_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            action = plan.actions[0]
            start = self._event(
                plan,
                action,
                "metrics-start",
                ReviewPlanExecutionEventKind.START,
                "2026-08-25T12:00:00Z",
            )
            complete = self._event(
                plan,
                action,
                "metrics-complete",
                ReviewPlanExecutionEventKind.COMPLETE,
                "2026-08-25T12:01:00Z",
                previous=start.content_address,
                checks=action.required_checks,
            )
            report = replay_review_workspace_plan_execution(plan, (start, complete))
            metrics = build_review_workspace_execution_metrics(plan, report)
            action_metrics = metrics.action_metrics[0]
            self.assertEqual(metrics.metrics_version, "review-workspace-execution-metrics-v1")
            self.assertEqual(metrics.event_count, 2)
            self.assertEqual(action_metrics.execution_seconds, 60)
            self.assertEqual(action_metrics.event_kind_counts["start"], 1)
            self.assertEqual(action_metrics.event_kind_counts["complete"], 1)
            self.assertEqual(action_metrics.completion_check_coverage_basis_points, 10_000)
            self.assertGreater(metrics.completion_basis_points, 0)
            self.assertIn(action.action_id, metrics.critical_path_action_ids)
            self.assertEqual(len(metrics.lane_metrics), 5)
            self.assertTrue(review_workspace_execution_metrics_capabilities()["critical_path_estimate"])
            self.assertEqual(
                review_workspace_execution_metrics_schema()["numeric_semantics"]["percentages"],
                "integer basis points where 10000 equals 100 percent",
            )
            self.assertIn("# Review Workspace Execution Metrics", render_review_workspace_execution_metrics_markdown(metrics))
            payloads = review_workspace_execution_metrics_export_payloads(metrics)
            self.assertEqual(set(payloads), {
                "review-workspace-execution-metrics.json",
                "review-workspace-execution-metrics.md",
                "review-workspace-execution-metrics.csv",
            })
            self.assertNotIn("agent_id", _keys(metrics.to_dict()))

    def test_cli_event_append_and_api_read_query_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            output = Path(directory) / "execution.json"
            self.assertEqual(
                main([
                    "review-workspace-plan-execution",
                    dossier.run_id,
                    "--data-root",
                    directory,
                    "--output",
                    str(output),
                ]),
                0,
            )
            initial = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(initial["event_count"], 0)
            action = plan.actions[0]
            event_output = Path(directory) / "event-execution.json"
            self.assertEqual(
                main([
                    "review-workspace-plan-event",
                    dossier.run_id,
                    "--data-root",
                    directory,
                    "--action-id",
                    action.action_id,
                    "--kind",
                    "start",
                    "--event-id",
                    "cli-start",
                    "--occurred-at",
                    "2026-08-25T12:00:00Z",
                    "--output",
                    str(event_output),
                ]),
                0,
            )
            self.assertEqual(json.loads(event_output.read_text(encoding="utf-8"))["event_count"], 1)
            release = Path(directory) / "execution-release"
            self.assertEqual(
                main([
                    "review-workspace-plan-execution-release",
                    dossier.run_id,
                    "--data-root",
                    directory,
                    "--output",
                    str(release),
                ]),
                0,
            )
            verification = Path(directory) / "execution-release-verification.json"
            self.assertEqual(
                main([
                    "review-workspace-plan-execution-release-verify",
                    str(release),
                    "--output",
                    str(verification),
                ]),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            release_query = Path(directory) / "execution-release-query.json"
            self.assertEqual(
                main([
                    "review-workspace-plan-execution-release-query",
                    str(release),
                    "--status",
                    "in_progress",
                    "--output",
                    str(release_query),
                ]),
                0,
            )
            self.assertEqual(json.loads(release_query.read_text(encoding="utf-8"))["total_count"], 1)
            release_events = Path(directory) / "execution-release-events.json"
            self.assertEqual(
                main([
                    "review-workspace-plan-execution-release-query",
                    str(release),
                    "--view",
                    "events",
                    "--kind",
                    "start",
                    "--output",
                    str(release_events),
                ]),
                0,
            )
            event_payload = json.loads(release_events.read_text(encoding="utf-8"))
            self.assertEqual(event_payload["total_count"], 1)
            self.assertEqual(event_payload["rows"][0]["sequence"], 0)
            release_metrics = Path(directory) / "execution-release-metrics.json"
            self.assertEqual(
                main([
                    "review-workspace-plan-execution-release-query",
                    str(release),
                    "--view",
                    "metrics",
                    "--output",
                    str(release_metrics),
                ]),
                0,
            )
            metrics_payload = json.loads(release_metrics.read_text(encoding="utf-8"))
            self.assertEqual(metrics_payload["metrics_version"], "review-workspace-execution-metrics-v1")
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/review-workspace/plan/execution/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["execution_version"], "review-workspace-execution-v1")
                params = urlencode({"status": "in_progress", "limit": "2"})
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution/query?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertEqual(payload["total_count"], 1)
                self.assertEqual(payload["rows"][0]["action_id"], action.action_id)
                params = urlencode({"view": "events", "kind": "start", "limit": "2"})
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution/query?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                timeline_payload = json.loads(response.read())
                self.assertEqual(timeline_payload["total_count"], 1)
                self.assertEqual(timeline_payload["rows"][0]["sequence"], 0)
                self.assertEqual(timeline_payload["rows"][0]["event"]["event_id"], "cli-start")
                params = urlencode({"view": "metrics"})
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution/query?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                live_metrics_payload = json.loads(response.read())
                self.assertEqual(live_metrics_payload["metrics_version"], "review-workspace-execution-metrics-v1")
                connection.request("GET", "/v1/review-workspace/plan/execution-release/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    json.loads(response.read())["version"],
                    "review-workspace-execution-release-schema-v1",
                )
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution-release",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                params = urlencode({"status": "in_progress", "limit": "2"})
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution-release/query?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total_count"], 1)
                params = urlencode({"view": "events", "kind": "start", "limit": "2"})
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution-release/query?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                release_timeline_payload = json.loads(response.read())
                self.assertEqual(release_timeline_payload["total_count"], 1)
                self.assertEqual(release_timeline_payload["rows"][0]["sequence"], 0)
                params = urlencode({"view": "metrics"})
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution-release/query?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                release_metrics_payload = json.loads(response.read())
                self.assertEqual(
                    release_metrics_payload["metrics_version"],
                    "review-workspace-execution-metrics-v1",
                )
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
