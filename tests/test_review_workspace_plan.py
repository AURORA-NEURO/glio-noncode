from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_exports import build_review_workspace_release, write_review_workspace_release
from glio_noncode.review_workspace_plan import (
    ReviewPlanState,
    ReviewWorkspacePlanConfig,
    ReviewWorkspacePlanQuery,
    build_review_workspace_plan,
    query_review_workspace_plan,
    review_workspace_plan_capabilities,
    review_workspace_plan_schema,
)
from glio_noncode.review_workspace_plan_exports import (
    render_review_workspace_plan_markdown,
    review_workspace_plan_export_payloads,
)
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


class ReviewWorkspacePlanTests(unittest.TestCase):
    def _report(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        return runtime, dossier, build_persisted_review_workspace(runtime, dossier.run_id)

    def test_plan_expands_queue_into_ordered_lanes_and_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            plan = build_review_workspace_plan(report)
            repeat = build_review_workspace_plan(report)
            self.assertTrue(plan.accepted)
            self.assertEqual(plan.state, ReviewPlanState.REVIEW)
            self.assertEqual(plan.queue_item_count, len(report.review_queue))
            self.assertGreater(plan.action_count, plan.queue_item_count)
            self.assertEqual(plan, repeat)
            self.assertEqual(
                tuple(item.sequence for item in plan.actions),
                tuple(range(plan.action_count)),
            )
            self.assertTrue(all(check.passed for check in plan.checks))
            actions_by_id = {item.action_id: item for item in plan.actions}
            self.assertTrue(all(
                actions_by_id[dependency].sequence < action.sequence
                for action in plan.actions
                for dependency in action.depends_on
            ))
            self.assertEqual(plan.to_dict(), repeat.to_dict())

    def test_cross_queue_evidence_dependencies_precede_hypothesis_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            public = report.to_dict()
            queue = dict(public["review_queue"][0])
            evidence_id = queue["evidence_ids"][0]
            evidence = next(item for item in public["evidence"] if item["evidence_id"] == evidence_id)
            public["review_queue"].append(
                {
                    "item_id": f"review:evidence:{evidence_id}",
                    "item_type": "evidence",
                    "target_id": evidence_id,
                    "priority": 0,
                    "reasons": ["evidence state requires review"],
                    "edge_ids": [evidence["edge_id"]],
                    "evidence_ids": [evidence_id],
                    "state": evidence["state"],
                    "content_address": "synthetic-queue-address",
                }
            )
            plan = build_review_workspace_plan(public)
            evidence_action = next(
                item for item in plan.actions
                if item.target_id == evidence_id and item.action_kind.value == "inspect"
            )
            hypothesis_action = next(
                item for item in plan.actions
                if item.target_id == queue["target_id"] and item.action_kind.value == "inspect"
            )
            self.assertIn(evidence_action.action_id, hypothesis_action.depends_on)
            self.assertLess(evidence_action.sequence, hypothesis_action.sequence)
            self.assertTrue(plan.accepted)

    def test_policy_switches_change_plan_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            compact = build_review_workspace_plan(
                report,
                config=ReviewWorkspacePlanConfig(
                    include_context_checks=False,
                    include_provenance_checks=False,
                    include_alternative_checks=False,
                    include_disposition_steps=False,
                ),
            )
            self.assertTrue(compact.accepted)
            self.assertTrue(all(item.action_kind.value == "inspect" for item in compact.actions))
            self.assertLess(compact.action_count, build_review_workspace_plan(report).action_count)

    def test_unaccepted_or_private_inputs_are_withheld(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            rejected = replace(report, accepted=False)
            blocked = build_review_workspace_plan(rejected)
            self.assertFalse(blocked.accepted)
            self.assertEqual(blocked.state, ReviewPlanState.BLOCKED)
            self.assertEqual(blocked.actions, ())
            private = report.to_dict()
            private["review_queue"][0]["subject_id"] = "hidden"
            with self.assertRaises(ValidationError):
                build_review_workspace_plan(private)

    def test_query_facets_exports_and_contract_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            plan = build_review_workspace_plan(report)
            query = query_review_workspace_plan(plan, ReviewWorkspacePlanQuery(lane="intake", limit=2))
            repeat = query_review_workspace_plan(plan, ReviewWorkspacePlanQuery(lane="intake", limit=2))
            self.assertTrue(query.accepted)
            self.assertEqual(query, repeat)
            self.assertIn("intake", query.facets["lanes"])
            payloads = review_workspace_plan_export_payloads(plan)
            self.assertEqual(payloads, review_workspace_plan_export_payloads(plan))
            self.assertIn("Ordered actions", render_review_workspace_plan_markdown(plan))
            self.assertNotIn("subject_id", _keys(plan.to_dict()))
            self.assertTrue(review_workspace_plan_capabilities()["dependency_ordering"])
            self.assertEqual(
                review_workspace_plan_schema()["plan_version"],
                "review-workspace-plan-v1",
            )
            with self.assertRaises(ValidationError):
                ReviewWorkspacePlanQuery(limit=0)

    def test_cli_and_http_plan_surfaces_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, report = self._report(directory)
            plan_output = Path(directory) / "plan.json"
            query_output = Path(directory) / "plan-query.json"
            self.assertEqual(
                main([
                    "review-workspace-plan",
                    dossier.run_id,
                    "--data-root",
                    directory,
                    "--output",
                    str(plan_output),
                ]),
                0,
            )
            self.assertEqual(
                json.loads(plan_output.read_text(encoding="utf-8"))["workspace_address"],
                report.content_address,
            )
            self.assertEqual(
                main([
                    "review-workspace-plan-query",
                    dossier.run_id,
                    "--data-root",
                    directory,
                    "--lane",
                    "intake",
                    "--limit",
                    "2",
                    "--output",
                    str(query_output),
                ]),
                0,
            )
            self.assertTrue(json.loads(query_output.read_text(encoding="utf-8"))["rows"])
            release_path = Path(directory) / "release"
            write_review_workspace_release(build_review_workspace_release(report), release_path)
            offline_output = Path(directory) / "offline-plan.json"
            self.assertEqual(
                main([
                    "review-workspace-release-plan",
                    str(release_path),
                    "--output",
                    str(offline_output),
                ]),
                0,
            )
            self.assertEqual(
                json.loads(offline_output.read_text(encoding="utf-8"))["workspace_address"],
                report.content_address,
            )
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/review-workspace/plan/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["plan_version"], "review-workspace-plan-v1")
                params = urlencode({"lane": "intake", "limit": "2"})
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/query?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertEqual(payload["plan_address"], json.loads(plan_output.read_text(encoding="utf-8"))["content_address"])
                self.assertTrue(payload["rows"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
