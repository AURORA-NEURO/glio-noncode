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
from glio_noncode.errors import ValidationError
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_execution import (
    ReviewPlanExecutionStore,
    replay_review_workspace_plan_execution,
)
from glio_noncode.review_workspace_execution_simulation import (
    REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS,
    ReviewWorkspaceExecutionSimulationProposal,
    review_workspace_execution_simulation_capabilities,
    review_workspace_execution_simulation_csv,
    review_workspace_execution_simulation_export_payloads,
    review_workspace_execution_simulation_from_mapping,
    review_workspace_execution_simulation_json,
    review_workspace_execution_simulation_schema,
    render_review_workspace_execution_simulation_markdown,
    simulate_review_workspace_plan_execution,
)
from glio_noncode.review_workspace_plan import build_review_workspace_plan
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class ReviewWorkspaceExecutionSimulationTests(unittest.TestCase):
    def _context(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        workspace = build_persisted_review_workspace(runtime, dossier.run_id)
        return runtime, dossier, build_review_workspace_plan(workspace)

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

    def test_sequential_success_is_hypothetical_and_receipted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            baseline = replay_review_workspace_plan_execution(plan)
            action = plan.actions[0]
            proposals = (
                self._proposal(action, "simulation-start", "start", "2026-08-25T12:00:00Z"),
                self._proposal(
                    action,
                    "simulation-complete",
                    "complete",
                    "2026-08-25T12:01:00Z",
                    check_ids=list(action.required_checks),
                ),
            )
            simulation = simulate_review_workspace_plan_execution(plan, baseline, proposals)
            self.assertTrue(simulation.accepted)
            self.assertTrue(simulation.no_side_effects)
            self.assertEqual(simulation.proposal_count, 2)
            self.assertEqual(simulation.evaluated_count, 2)
            self.assertEqual(simulation.accepted_proposal_count, 2)
            self.assertEqual(simulation.rejected_proposal_count, 0)
            self.assertEqual(simulation.projected_event_count, 2)
            self.assertEqual(simulation.applied_event_ids, ("simulation-start", "simulation-complete"))
            self.assertEqual(simulation.results[0].preflight_disposition, "available")
            self.assertEqual(simulation.results[1].resulting_status, "completed")
            self.assertEqual(baseline.event_count, 0)
            self.assertEqual(baseline.events, ())
            self.assertEqual(simulation.final_report.event_count, 2)
            payload = simulation.to_dict(include_report=True)
            self.assertIn("final_report", payload)
            self.assertEqual(
                review_workspace_execution_simulation_json(simulation),
                review_workspace_execution_simulation_json(simulation),
            )
            hydrated = review_workspace_execution_simulation_from_mapping(
                simulation.to_dict()
            )
            self.assertEqual(hydrated.to_dict(), simulation.to_dict())
            hydrated_with_report = review_workspace_execution_simulation_from_mapping(payload)
            self.assertIsNotNone(hydrated_with_report.final_report)
            self.assertEqual(hydrated_with_report.final_execution_address, simulation.final_execution_address)

    def test_first_failure_stops_and_reports_unevaluated_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            baseline = replay_review_workspace_plan_execution(plan)
            action = plan.actions[0]
            proposals = (
                self._proposal(action, "failure-start", "start", "2026-08-25T12:00:00Z"),
                self._proposal(action, "failure-complete", "complete", "2026-08-25T12:01:00Z"),
                self._proposal(
                    action,
                    "failure-block",
                    "block",
                    "2026-08-25T12:02:00Z",
                    reason="tail must not be evaluated",
                ),
            )
            simulation = simulate_review_workspace_plan_execution(plan, baseline, proposals)
            self.assertFalse(simulation.accepted)
            self.assertTrue(simulation.stopped_on_error)
            self.assertEqual(simulation.rejected_proposal_index, 1)
            self.assertEqual(simulation.evaluated_count, 2)
            self.assertEqual(simulation.accepted_proposal_count, 1)
            self.assertEqual(simulation.rejected_proposal_count, 1)
            self.assertEqual(simulation.projected_event_count, 1)
            self.assertEqual(simulation.results[1].error_code, "required_checks")
            self.assertFalse(simulation.results[2].evaluated)
            self.assertEqual(simulation.results[2].error_code, "not_evaluated")
            self.assertEqual(simulation.final_report.event_count, 1)
            self.assertEqual(baseline.event_count, 0)

    def test_stale_predecessor_and_public_boundary_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            baseline = replay_review_workspace_plan_execution(plan)
            action = plan.actions[0]
            stale = simulate_review_workspace_plan_execution(
                plan,
                baseline,
                [
                    self._proposal(
                        action,
                        "stale-start",
                        "start",
                        "2026-08-25T12:00:00Z",
                        expected_previous_event_address="sha256:stale",
                    )
                ],
            )
            self.assertFalse(stale.accepted)
            self.assertEqual(stale.results[0].error_code, "stale_predecessor")
            with self.assertRaises(ValidationError):
                ReviewWorkspaceExecutionSimulationProposal.from_mapping(
                    self._proposal(
                        action,
                        "private-proposal",
                        "start",
                        "2026-08-25T12:00:00Z",
                        agent_id="forbidden",
                    )
                )
            with self.assertRaises(ValidationError):
                simulate_review_workspace_plan_execution(
                    plan,
                    baseline,
                    [
                        self._proposal(
                            action,
                            f"bounded-{index}",
                            "start",
                            "2026-08-25T12:00:00Z",
                        )
                        for index in range(REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS + 1)
                    ],
                )

    def test_exports_schema_capabilities_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, plan = self._context(directory)
            simulation = simulate_review_workspace_plan_execution(
                plan,
                replay_review_workspace_plan_execution(plan),
            )
            payloads = review_workspace_execution_simulation_export_payloads(simulation)
            self.assertEqual(
                set(payloads),
                {
                    "review-workspace-execution-simulation.json",
                    "review-workspace-execution-simulation.md",
                    "review-workspace-execution-simulation.csv",
                },
            )
            self.assertEqual(json.loads(review_workspace_execution_simulation_json(simulation)), simulation.to_dict())
            self.assertEqual(review_workspace_execution_simulation_csv(simulation).splitlines()[0].split(",")[0], "proposal_index")
            self.assertIn("hypothetical replay", render_review_workspace_execution_simulation_markdown(simulation))
            self.assertTrue(review_workspace_execution_simulation_capabilities()["side_effect_free"])
            self.assertTrue(review_workspace_execution_simulation_schema()["failure_policy"]["baseline_is_unchanged"])
            tampered = simulation.to_dict()
            tampered["accepted"] = False
            with self.assertRaises(ValidationError):
                review_workspace_execution_simulation_from_mapping(tampered)

    def test_cli_and_api_simulation_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            action = plan.actions[0]
            proposal_path = Path(directory) / "proposals.json"
            proposal_path.write_text(
                json.dumps([self._proposal(action, "surface-start", "start", "2026-08-25T12:00:00Z")]),
                encoding="utf-8",
            )
            output = Path(directory) / "simulation.json"
            self.assertEqual(
                main(
                    [
                        "review-workspace-plan-execution-simulate",
                        dossier.run_id,
                        "--data-root",
                        directory,
                        "--proposals",
                        str(proposal_path),
                        "--include-report",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["projected_event_count"], 1)
            persisted = ReviewPlanExecutionStore(runtime.store.root).read_events(plan)
            self.assertEqual(persisted, ())
            schema_output = Path(directory) / "simulation-schema.json"
            self.assertEqual(
                main(
                    [
                        "review-workspace-plan-execution-simulation-schema",
                        "--output",
                        str(schema_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(schema_output.read_text(encoding="utf-8"))["version"],
                "review-workspace-execution-simulation-schema-v1",
            )
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                params = urlencode(
                    {
                        "proposals": json.dumps(
                            [self._proposal(action, "api-start", "start", "2026-08-25T12:00:00Z")]
                        ),
                        "include_report": "true",
                    }
                )
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution/simulate?{params}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_payload = json.loads(response.read())
                self.assertTrue(api_payload["accepted"])
                self.assertEqual(api_payload["projected_event_count"], 1)
                connection.request(
                    "GET",
                    "/v1/review-workspace/plan/execution/simulation/capabilities",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["side_effect_free"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
