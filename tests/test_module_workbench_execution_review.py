"""Regression coverage for module-level execution review routing."""

from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution import (
    apply_module_workbench_execution_commands,
    build_module_workbench_execution,
    execution_command,
)
from glio_noncode.module_workbench_execution_contracts import ModuleWorkbenchExecutionState
from glio_noncode.module_workbench_execution_review import (
    build_module_workbench_execution_review,
    module_workbench_execution_review_capabilities,
    module_workbench_execution_review_csv,
    module_workbench_execution_review_json,
    module_workbench_execution_review_schema,
    query_module_workbench_execution_review,
    render_module_workbench_execution_review_markdown,
    verify_module_workbench_execution_review,
)
from glio_noncode.module_workbench_execution_review_contracts import (
    ModuleWorkbenchExecutionReviewState,
)
from glio_noncode.module_workbench_portfolio import build_module_workbench_portfolio
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_review_conserves_module_rollups_and_routes_ready_tasks(self) -> None:
        _report, ledger = self.fixture.ledger()
        review = build_module_workbench_execution_review(ledger)
        verify_module_workbench_execution_review(review)
        self.assertGreaterEqual(review.module_count, 1)
        self.assertEqual(
            review.next_task_count, sum(len(item.next_task_ids) for item in review.items)
        )
        self.assertEqual(
            sum(
                (
                    review.attention_count,
                    review.evidence_pending_count,
                    review.ready_count,
                    review.waiting_count,
                    review.verify_count,
                    review.complete_count,
                    review.superseded_count,
                )
            ),
            review.module_count,
        )
        self.assertTrue(
            any(
                item.review_state is ModuleWorkbenchExecutionReviewState.READY
                for item in review.items
            )
        )
        self.assertTrue(any(item.next_task_ids for item in review.items))

    def test_blocked_module_routes_to_attention_with_details(self) -> None:
        _report, ledger = self.fixture.ledger()
        target = next(
            item for item in ledger.items if item.state is ModuleWorkbenchExecutionState.READY
        )
        blocked = apply_module_workbench_execution_commands(
            ledger,
            (execution_command(target.task_id, "block", "requires dependency review"),),
        )
        review = build_module_workbench_execution_review(blocked)
        module = next(item for item in review.items if item.module_id == target.module_id)
        self.assertEqual(module.review_state, ModuleWorkbenchExecutionReviewState.ATTENTION)
        self.assertEqual(module.blocker_details, ("requires dependency review",))
        self.assertIn(target.task_id, module.next_task_ids)
        self.assertEqual(review.attention_count, 1)

    def test_in_progress_module_routes_to_evidence_pending(self) -> None:
        _report, ledger = self.fixture.ledger()
        target = next(
            item for item in ledger.items if item.state is ModuleWorkbenchExecutionState.READY
        )
        active = apply_module_workbench_execution_commands(
            ledger,
            (execution_command(target.task_id, "start", "begin implementation"),),
        )
        review = build_module_workbench_execution_review(active)
        module = next(item for item in review.items if item.module_id == target.module_id)
        self.assertEqual(module.review_state, ModuleWorkbenchExecutionReviewState.EVIDENCE_PENDING)
        self.assertIn(target.task_id, module.next_task_ids)
        self.assertIn("await completion evidence", module.detail)

    def test_completed_module_can_become_complete(self) -> None:
        report = self.fixture.report()
        portfolio = build_module_workbench_portfolio(
            report,
            capacity=100,
            max_tasks_per_module=1,
        )
        ledger = build_module_workbench_execution(report, portfolio)
        target = next(
            item for item in ledger.items if item.state is ModuleWorkbenchExecutionState.READY
        )
        current = apply_module_workbench_execution_commands(
            ledger,
            (
                execution_command(target.task_id, "start", "begin implementation"),
                execution_command(
                    target.task_id,
                    "complete",
                    "close implementation",
                    evidence_addresses=("receipt:one", "receipt:two"),
                ),
            ),
        )
        review = build_module_workbench_execution_review(current)
        module = next(item for item in review.items if item.module_id == target.module_id)
        self.assertEqual(module.review_state, ModuleWorkbenchExecutionReviewState.COMPLETE)
        self.assertEqual(module.completion_percent, 100.0)
        self.assertEqual(module.next_task_ids, ())

    def test_waiting_state_is_preserved_for_dependent_tasks(self) -> None:
        _report, ledger = self.fixture.ledger()
        root = next(
            item for item in ledger.items if item.state is ModuleWorkbenchExecutionState.READY
        )
        waiting_ledger = apply_module_workbench_execution_commands(
            ledger,
            (execution_command(root.task_id, "skip", "deferred for a later wave"),),
        )
        dependent = next(item for item in waiting_ledger.items if item.prerequisites)
        review = build_module_workbench_execution_review(waiting_ledger)
        module = next(item for item in review.items if item.module_id == dependent.module_id)
        self.assertEqual(module.review_state, ModuleWorkbenchExecutionReviewState.WAITING)
        self.assertEqual(module.ready_count, 0)
        self.assertIn(dependent.task_id, module.next_task_ids)

    def test_all_skipped_module_is_closed_without_being_superseded(self) -> None:
        _report, ledger = self.fixture.ledger()
        skipped = apply_module_workbench_execution_commands(
            ledger,
            tuple(
                execution_command(item.task_id, "skip", "deferred outside this release")
                for item in ledger.items
            ),
        )
        review = build_module_workbench_execution_review(skipped)
        self.assertTrue(
            all(
                item.review_state is ModuleWorkbenchExecutionReviewState.COMPLETE
                for item in review.items
            )
        )
        self.assertEqual(review.complete_count, review.module_count)
        self.assertEqual(review.superseded_count, 0)

    def test_queries_support_module_task_and_summary_resources(self) -> None:
        _report, ledger = self.fixture.ledger()
        review = build_module_workbench_execution_review(ledger)
        first = review.items[0]
        modules = query_module_workbench_execution_review(
            review,
            resource="modules",
            module_id=first.module_id,
        )
        self.assertEqual(modules["total"], 1)
        tasks = query_module_workbench_execution_review(review, resource="tasks", limit=100)
        self.assertEqual(tasks["total"], review.next_task_count)
        summary = query_module_workbench_execution_review(review, resource="summary")
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["items"][0]["module_count"], review.module_count)
        self.assertEqual(
            query_module_workbench_execution_review(
                review,
                module_id=first.module_id,
                review_state=first.review_state.value,
            )["total"],
            1,
        )

    def test_queries_reject_unknown_resources_and_invalid_limits(self) -> None:
        _report, ledger = self.fixture.ledger()
        review = build_module_workbench_execution_review(ledger)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_review(review, resource="events")
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_review(review, limit=513)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_review(review, offset=-1)

    def test_exports_keep_review_order_and_public_fields(self) -> None:
        _report, ledger = self.fixture.ledger()
        review = build_module_workbench_execution_review(ledger)
        self.assertIn('"module_count"', module_workbench_execution_review_json(review))
        self.assertIn("module_id", module_workbench_execution_review_csv(review))
        self.assertIn(
            "Module Workbench Execution Review",
            render_module_workbench_execution_review_markdown(review),
        )
        self.assertEqual(
            module_workbench_execution_review_schema()["resources"], ["modules", "tasks", "summary"]
        )
        capabilities = module_workbench_execution_review_capabilities()
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertTrue(capabilities["identity_free"])

    def test_tampered_review_address_is_rejected(self) -> None:
        _report, ledger = self.fixture.ledger()
        review = build_module_workbench_execution_review(ledger)
        object.__setattr__(review.items[0], "detail", "tampered")
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_review(review)
