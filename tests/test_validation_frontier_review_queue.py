"""Review queue coverage for the Domain 13 planning frontier."""

from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.validation_frontier_contracts import default_validation_frontier_contracts
from glio_noncode.validation_frontier_fixture_eval import evaluate_validation_frontier_fixture
from glio_noncode.validation_frontier_policy import default_validation_frontier_policy
from glio_noncode.validation_frontier_public_data import (
    ValidationFrontierOperation,
    ValidationFrontierRole,
    default_validation_frontier_fixture,
)
from glio_noncode.validation_frontier_review_queue import (
    ValidationFrontierReviewDisposition,
    ValidationFrontierReviewPriority,
    build_validation_frontier_review_queue,
)


class ValidationFrontierReviewQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_validation_frontier_fixture()
        self.evaluation = evaluate_validation_frontier_fixture(self.fixture)
        policy = default_validation_frontier_policy(default_validation_frontier_contracts())
        self.decisions = policy.decide(self.evaluation)
        self.queue = build_validation_frontier_review_queue(self.fixture, self.evaluation, self.decisions)

    def test_queue_is_accepted_and_content_addressed(self) -> None:
        self.assertTrue(self.queue.accepted)
        self.assertTrue(self.queue.content_address.startswith("sha256:"))
        self.assertEqual(len(self.queue.checks), 6)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.queue.items))

    def test_queue_covers_every_execution_once(self) -> None:
        self.assertEqual(len(self.queue.items), 16)
        self.assertEqual({item.record_id for item in self.queue.items}, set(self.evaluation.execution_map()))
        self.assertEqual(len({item.item_id for item in self.queue.items}), 16)
        self.assertEqual(self.queue.fixture_id, self.fixture.fixture_id)

    def test_positive_items_are_ready_for_bounded_review(self) -> None:
        self.assertEqual(len(self.queue.positive_items), 4)
        self.assertEqual(len(self.queue.ready_items), 4)
        self.assertTrue(all(item.accepted for item in self.queue.positive_items))
        self.assertTrue(all(item.disposition is ValidationFrontierReviewDisposition.READY_FOR_REVIEW for item in self.queue.positive_items))
        self.assertEqual({item.next_action for item in self.queue.positive_items}, {"route to bounded review"})

    def test_control_items_are_held_for_repair(self) -> None:
        self.assertEqual(len(self.queue.control_items), 12)
        self.assertEqual(len(self.queue.blocked_items), 12)
        self.assertTrue(all(item.blocked for item in self.queue.control_items))
        self.assertTrue(all(item.disposition is ValidationFrontierReviewDisposition.HOLD_FOR_REPAIR for item in self.queue.control_items))
        self.assertTrue(all(item.next_action == "resolve issue codes and replay" for item in self.queue.control_items))

    def test_operation_views_preserve_four_operation_surface(self) -> None:
        for operation in ValidationFrontierOperation:
            rows = self.queue.by_operation(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual({item.role for item in rows}, {ValidationFrontierRole.POSITIVE, ValidationFrontierRole.CONTROL})
            self.assertEqual(len(tuple(item for item in rows if item.accepted)), 1)
            self.assertEqual(len(tuple(item for item in rows if item.blocked)), 3)

    def test_priority_routes_positive_work_by_operation(self) -> None:
        priorities = {item.record_id: item.priority for item in self.queue.positive_items}
        self.assertEqual(priorities["C01-POS-001"], ValidationFrontierReviewPriority.EVIDENCE)
        self.assertEqual(priorities["C02-POS-001"], ValidationFrontierReviewPriority.ROUTING)
        self.assertEqual(priorities["C03-POS-001"], ValidationFrontierReviewPriority.DESIGN)
        self.assertEqual(priorities["C04-POS-001"], ValidationFrontierReviewPriority.DESIGN)
        self.assertTrue(all(item.priority is ValidationFrontierReviewPriority.CONTROL for item in self.queue.control_items))

    def test_next_item_is_a_control_with_repair_action(self) -> None:
        item = self.queue.next_item()
        self.assertTrue(item.blocked)
        self.assertIn("CTRL", item.record_id)
        self.assertEqual(item.next_action, "resolve issue codes and replay")

    def test_next_item_after_ready_only_queue_is_stable(self) -> None:
        ready = tuple(item for item in self.queue.items if item.accepted)
        body = self.queue.__class__(self.queue.queue_id + "-ready", self.queue.fixture_id, ready, self.queue.checks, self.queue.content_address)
        self.assertEqual(body.next_item().record_id, "C01-POS-001")

    def test_issue_vocabulary_is_sorted_and_complete(self) -> None:
        self.assertEqual(self.queue.issue_codes(), tuple(sorted(self.queue.issue_codes())))
        self.assertIn("context_mismatch", self.queue.issue_codes())
        self.assertIn("max_constructs_exceeded", self.queue.issue_codes())
        self.assertIn("insert_length", self.queue.issue_codes())
        self.assertEqual(len(self.queue.issue_codes()), 10)

    def test_serialized_summary_exposes_operational_counts(self) -> None:
        body = self.queue.to_dict()
        self.assertEqual(body["ready_count"], 4)
        self.assertEqual(body["blocked_count"], 12)
        self.assertEqual(body["positive_count"], 4)
        self.assertEqual(body["control_count"], 12)
        self.assertEqual(body["next_item_id"], self.queue.next_item().item_id)
        self.assertTrue(body["accepted"])

    def test_empty_queue_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.queue.__class__("empty", self.fixture.fixture_id, (), (), "sha256:empty")

    def test_empty_queue_id_is_rejected_by_builder(self) -> None:
        with self.assertRaises(ValidationError):
            build_validation_frontier_review_queue(self.fixture, self.evaluation, self.decisions, queue_id="")

    def test_different_queue_ids_change_queue_address(self) -> None:
        second = build_validation_frontier_review_queue(self.fixture, self.evaluation, self.decisions, queue_id="validation-frontier-review-queue-2")
        self.assertNotEqual(self.queue.content_address, second.content_address)
        self.assertEqual(tuple(item.to_dict() for item in self.queue.items), tuple(item.to_dict() for item in second.items))

    def test_item_to_dict_retains_state_and_blocker_fields(self) -> None:
        control = next(item for item in self.queue.items if item.record_id == "C02-CTRL-002")
        body = control.to_dict()
        self.assertEqual(body["record_id"], "C02-CTRL-002")
        self.assertEqual(body["issue_codes"], ["missing_controls", "missing_readouts"])
        self.assertTrue(body["blocked"])
        self.assertFalse(body["accepted"])

    def test_check_addresses_are_stable_for_same_inputs(self) -> None:
        second = build_validation_frontier_review_queue(self.fixture, self.evaluation, self.decisions)
        self.assertEqual(tuple(item.content_address for item in self.queue.checks), tuple(item.content_address for item in second.checks))

    def test_queue_is_replayable_from_the_same_evaluation(self) -> None:
        second_evaluation = evaluate_validation_frontier_fixture(self.fixture)
        second = build_validation_frontier_review_queue(self.fixture, second_evaluation, self.decisions)
        self.assertEqual(self.queue.content_address, second.content_address)
        self.assertEqual(self.queue.to_dict(), second.to_dict())

    def test_issue_codes_bind_to_the_control_rows(self) -> None:
        for item in self.queue.control_items:
            execution = self.evaluation.execution_map()[item.record_id]
            self.assertEqual(item.issue_codes, execution.issue_codes)
            self.assertTrue(item.issue_codes)

    def test_positive_rows_do_not_inherit_control_issues(self) -> None:
        self.assertTrue(all(item.issue_codes == () for item in self.queue.positive_items))


if __name__ == "__main__":
    unittest.main()
