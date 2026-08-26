"""Contract tests for the review-workspace execution transition frontier."""

from __future__ import annotations

import json
import tempfile
import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_execution import (
    ReviewPlanExecutionEventKind,
    build_review_plan_execution_event,
    replay_review_workspace_plan_execution,
)
from glio_noncode.review_workspace_execution_transitions import (
    ReviewWorkspaceExecutionTransitionDisposition,
    ReviewWorkspaceExecutionTransitionsQuery,
    build_review_workspace_execution_transitions,
    diff_review_workspace_execution_transitions,
    query_review_workspace_execution_transitions,
    render_review_workspace_execution_transitions_markdown,
    review_workspace_execution_transitions_capabilities,
    review_workspace_execution_transitions_csv,
    review_workspace_execution_transitions_diff_capabilities,
    review_workspace_execution_transitions_diff_schema,
    review_workspace_execution_transitions_export_payloads,
    review_workspace_execution_transitions_from_mapping,
    review_workspace_execution_transitions_json,
    review_workspace_execution_transitions_schema,
)
from glio_noncode.review_workspace_plan import build_review_workspace_plan
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class ReviewWorkspaceExecutionTransitionsTests(unittest.TestCase):
    def _context(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        workspace = build_persisted_review_workspace(runtime, dossier.run_id)
        plan = build_review_workspace_plan(workspace)
        report = replay_review_workspace_plan_execution(plan)
        return plan, report

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

    def test_initial_frontier_expands_every_action_into_a_state_machine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan, report = self._context(directory)
            frontier = build_review_workspace_execution_transitions(plan, report)
            self.assertTrue(frontier.accepted)
            self.assertEqual(frontier.action_count, len(plan.actions))
            self.assertEqual(frontier.option_count, len(plan.actions) * 5)
            self.assertEqual(
                frontier.transition_counts,
                {
                    "block": len(plan.actions),
                    "complete": len(plan.actions),
                    "reopen": len(plan.actions),
                    "skip": len(plan.actions),
                    "start": len(plan.actions),
                },
            )
            self.assertEqual(
                len(frontier.recommended_action_ids),
                len(plan.actions),
            )
            first = frontier.actions[0]
            self.assertTrue(first.ready)
            start = next(item for item in first.options if item.kind.value == "start")
            self.assertEqual(
                start.disposition,
                ReviewWorkspaceExecutionTransitionDisposition.AVAILABLE,
            )
            self.assertTrue(start.executable_without_additional_input)
            complete = next(item for item in first.options if item.kind.value == "complete")
            self.assertEqual(
                complete.disposition,
                ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_CHECKS,
            )
            self.assertEqual(complete.required_check_ids, first_action(plan).required_checks)
            reopen = next(item for item in first.options if item.kind.value == "reopen")
            self.assertFalse(reopen.permitted)
            self.assertEqual(
                reopen.disposition,
                ReviewWorkspaceExecutionTransitionDisposition.NOT_ALLOWED,
            )

    def test_dependency_wait_and_required_inputs_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan, report = self._context(directory)
            dependent = next(item for item in plan.actions if item.depends_on)
            action = next(item for item in report.actions if item.action_id == dependent.action_id)
            frontier = build_review_workspace_execution_transitions(plan, report)
            row = next(item for item in frontier.actions if item.action_id == dependent.action_id)
            self.assertFalse(row.ready)
            self.assertEqual(row.unresolved_dependencies, action.unresolved_dependencies)
            start = next(item for item in row.options if item.kind is ReviewPlanExecutionEventKind.START)
            complete = next(item for item in row.options if item.kind is ReviewPlanExecutionEventKind.COMPLETE)
            self.assertEqual(
                start.disposition,
                ReviewWorkspaceExecutionTransitionDisposition.WAITING_DEPENDENCIES,
            )
            self.assertEqual(start.missing_dependency_ids, action.unresolved_dependencies)
            self.assertEqual(
                complete.disposition,
                ReviewWorkspaceExecutionTransitionDisposition.WAITING_DEPENDENCIES,
            )
            self.assertEqual(complete.missing_dependency_ids, action.unresolved_dependencies)
            block = next(item for item in row.options if item.kind is ReviewPlanExecutionEventKind.BLOCK)
            self.assertEqual(
                block.disposition,
                ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_REASON,
            )
            self.assertTrue(block.requires_reason)

    def test_progressed_report_updates_previous_event_and_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan, initial = self._context(directory)
            first = plan.actions[0]
            started = self._event(
                plan,
                first,
                "transition-start",
                ReviewPlanExecutionEventKind.START,
                "2026-08-25T12:00:00Z",
            )
            completed = self._event(
                plan,
                first,
                "transition-complete",
                ReviewPlanExecutionEventKind.COMPLETE,
                "2026-08-25T12:01:00Z",
                previous=started.content_address,
                checks=first.required_checks,
            )
            progressed = replay_review_workspace_plan_execution(plan, (started, completed))
            frontier = build_review_workspace_execution_transitions(plan, progressed)
            row = frontier.actions[0]
            self.assertEqual(row.status.value, "completed")
            self.assertEqual(row.last_event_id, "transition-complete")
            self.assertEqual(row.previous_event_address, completed.content_address)
            self.assertEqual(row.recommended_kind, ReviewPlanExecutionEventKind.REOPEN)
            recommended = next(
                item for item in row.options if item.kind is ReviewPlanExecutionEventKind.REOPEN
            )
            self.assertEqual(recommended.disposition, ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_REASON)
            self.assertFalse(recommended.executable_without_additional_input)
            self.assertNotEqual(initial.content_address, progressed.content_address)

    def test_query_is_bounded_and_facets_are_complete_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan, report = self._context(directory)
            frontier = build_review_workspace_execution_transitions(plan, report)
            query = ReviewWorkspaceExecutionTransitionsQuery(
                kind="start",
                disposition="available",
                executable=True,
                limit=1,
            )
            result = query_review_workspace_execution_transitions(frontier, query)
            self.assertTrue(result.accepted)
            self.assertEqual(result.total_count, len(frontier.ready_action_ids))
            self.assertEqual(len(result.rows), 1)
            self.assertEqual(result.facets["kinds"], {"start": result.total_count})
            self.assertFalse(result.facets["dispositions"].get("not_allowed", 0))
            self.assertEqual(result.query.to_dict(), query.to_dict())
            self.assertTrue(result.has_more == (result.total_count > 1))
            with self.assertRaises(ValidationError):
                ReviewWorkspaceExecutionTransitionsQuery(limit=0)
            with self.assertRaises(ValidationError):
                ReviewWorkspaceExecutionTransitionsQuery(kind="unknown")
            with self.assertRaises(ValidationError):
                ReviewWorkspaceExecutionTransitionsQuery(priorities=(9,))

    def test_exports_and_hydration_are_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan, report = self._context(directory)
            frontier = build_review_workspace_execution_transitions(plan, report)
            hydrated = review_workspace_execution_transitions_from_mapping(frontier.to_dict())
            self.assertEqual(hydrated.to_dict(), frontier.to_dict())
            self.assertEqual(
                json.loads(review_workspace_execution_transitions_json(frontier)),
                frontier.to_dict(),
            )
            csv_payload = review_workspace_execution_transitions_csv(frontier)
            self.assertTrue(csv_payload.startswith("transition_id,action_id"))
            self.assertEqual(csv_payload.count("\n"), frontier.option_count + 1)
            markdown = render_review_workspace_execution_transitions_markdown(frontier)
            self.assertIn("Review workspace execution transitions", markdown)
            self.assertIn("read-only preflight", markdown)
            payloads = review_workspace_execution_transitions_export_payloads(frontier)
            self.assertEqual(
                set(payloads),
                {
                    "review-workspace-execution-transitions.json",
                    "review-workspace-execution-transitions.csv",
                    "review-workspace-execution-transitions.md",
                },
            )
            forged = frontier.to_dict()
            forged["option_count"] = int(forged["option_count"]) + 1
            with self.assertRaises(ValidationError):
                review_workspace_execution_transitions_from_mapping(forged)
            forged_version = frontier.to_dict()
            forged_version["transitions_version"] = "forged-transition-version"
            with self.assertRaises(ValidationError):
                review_workspace_execution_transitions_from_mapping(forged_version)

    def test_diff_reports_changed_options_and_count_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan, initial = self._context(directory)
            first = plan.actions[0]
            started = self._event(
                plan,
                first,
                "diff-start",
                ReviewPlanExecutionEventKind.START,
                "2026-08-25T12:00:00Z",
            )
            progressed = replay_review_workspace_plan_execution(plan, (started,))
            left = build_review_workspace_execution_transitions(plan, initial)
            right = build_review_workspace_execution_transitions(plan, progressed)
            diff = diff_review_workspace_execution_transitions(left, right)
            self.assertTrue(diff.accepted)
            self.assertTrue(diff.changed_transition_ids)
            self.assertEqual(diff.count_deltas["action_count"], 0)
            self.assertEqual(diff.count_deltas["option_count"], 0)
            self.assertTrue(diff.recommendation_changed)
            first_diff = next(item for item in diff.action_diffs if item.action_id == first.action_id)
            self.assertTrue(first_diff.changed)
            self.assertEqual(first_diff.left_status, "open")
            self.assertEqual(first_diff.right_status, "in_progress")
            self.assertEqual(diff.left_execution_address, initial.content_address)
            self.assertEqual(diff.right_execution_address, progressed.content_address)

    def test_contract_metadata_declares_preflight_and_boundary_rules(self) -> None:
        schema = review_workspace_execution_transitions_schema()
        capabilities = review_workspace_execution_transitions_capabilities()
        diff_schema = review_workspace_execution_transitions_diff_schema()
        diff_capabilities = review_workspace_execution_transitions_diff_capabilities()
        self.assertEqual(schema["version"], "review-workspace-execution-transitions-schema-v1")
        self.assertEqual(schema["query"]["version"], "review-workspace-execution-transitions-query-v1")
        self.assertTrue(schema["option_contract"]["state_machine_reconciled"])
        self.assertTrue(schema["option_contract"]["dependency_preconditions_explicit"])
        self.assertFalse(schema["boundary"]["agent_identity"])
        self.assertTrue(capabilities["state_machine_preflight"])
        self.assertTrue(capabilities["required_check_preflight"])
        self.assertTrue(capabilities["transition_diff"])
        self.assertEqual(diff_schema["version"], "review-workspace-execution-transitions-diff-schema-v1")
        self.assertTrue(diff_capabilities["per_action_recommendation_diff"])


def first_action(plan):
    """Return the first declared action for concise assertions."""

    return plan.actions[0]


if __name__ == "__main__":
    unittest.main()
