"""Depth and review queue tests for the Domain 14 lifecycle frontier."""

from __future__ import annotations

import unittest

from glio_noncode.evidence_lifecycle_frontier_contracts import default_evidence_lifecycle_contracts
from glio_noncode.evidence_lifecycle_frontier_depth import audit_evidence_lifecycle_depth
from glio_noncode.evidence_lifecycle_frontier_fixture_eval import (
    evaluate_evidence_lifecycle_fixture,
)
from glio_noncode.evidence_lifecycle_frontier_policy import default_evidence_lifecycle_policy
from glio_noncode.evidence_lifecycle_frontier_public_data import (
    EvidenceLifecycleOperation,
    EvidenceLifecycleRole,
    default_evidence_lifecycle_fixture,
)
from glio_noncode.evidence_lifecycle_frontier_review_queue import (
    EvidenceLifecycleReviewDisposition,
    EvidenceLifecycleReviewPriority,
    build_evidence_lifecycle_review_queue,
)


class EvidenceLifecycleFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_evidence_lifecycle_fixture()
        self.evaluation = evaluate_evidence_lifecycle_fixture(self.fixture)
        self.policy = default_evidence_lifecycle_policy()
        self.queue = build_evidence_lifecycle_review_queue(self.fixture, self.evaluation, self.policy.decide(self.evaluation))

    def test_depth_audit_has_twenty_checks(self) -> None:
        report = audit_evidence_lifecycle_depth()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 20)
        self.assertEqual(report.passed_count, 20)
        self.assertEqual(report.failed_check_ids, ())

    def test_queue_is_accepted_and_addressed(self) -> None:
        self.assertTrue(self.queue.accepted)
        self.assertTrue(self.queue.content_address.startswith("sha256:"))
        self.assertEqual(len(self.queue.checks), 6)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.queue.items))

    def test_queue_covers_every_execution_once(self) -> None:
        self.assertEqual(len(self.queue.items), 16)
        self.assertEqual({item.record_id for item in self.queue.items}, set(self.evaluation.execution_map()))
        self.assertEqual(len({item.item_id for item in self.queue.items}), 16)

    def test_positive_items_are_ready_for_bounded_review(self) -> None:
        positives = self.queue.ready_items
        self.assertEqual(len(positives), 4)
        self.assertTrue(all(item.role is EvidenceLifecycleRole.POSITIVE for item in positives))
        self.assertTrue(all(item.disposition is EvidenceLifecycleReviewDisposition.READY_FOR_REVIEW for item in positives))
        self.assertEqual({item.next_action for item in positives}, {"route to bounded review"})

    def test_controls_are_held_for_repair(self) -> None:
        controls = self.queue.blocked_items
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(item.role is EvidenceLifecycleRole.CONTROL for item in controls))
        self.assertTrue(all(item.disposition is EvidenceLifecycleReviewDisposition.HOLD_FOR_REPAIR for item in controls))
        self.assertTrue(all(item.next_action == "resolve issue codes and replay" for item in controls))

    def test_operation_views_preserve_one_positive_and_three_controls(self) -> None:
        for operation in EvidenceLifecycleOperation:
            rows = self.queue.by_operation(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len(tuple(item for item in rows if item.role is EvidenceLifecycleRole.POSITIVE)), 1)
            self.assertEqual(len(tuple(item for item in rows if item.role is EvidenceLifecycleRole.CONTROL)), 3)

    def test_priority_assignment_is_explicit(self) -> None:
        positive_priority = {item.record_id: item.priority for item in self.queue.ready_items}
        self.assertEqual(positive_priority["C01-POS-001"], EvidenceLifecycleReviewPriority.CITATION)
        self.assertEqual(positive_priority["C02-POS-001"], EvidenceLifecycleReviewPriority.GRAPH)
        self.assertEqual(positive_priority["C03-POS-001"], EvidenceLifecycleReviewPriority.EDGE)
        self.assertEqual(positive_priority["C04-POS-001"], EvidenceLifecycleReviewPriority.DISAGREEMENT)
        self.assertTrue(all(item.priority is EvidenceLifecycleReviewPriority.CONTROL for item in self.queue.blocked_items))

    def test_next_item_prefers_held_controls(self) -> None:
        item = self.queue.next_item()
        self.assertTrue(item.blocked)
        self.assertIn("CTRL", item.record_id)
        self.assertEqual(item.priority, EvidenceLifecycleReviewPriority.CONTROL)

    def test_issue_codes_are_sorted_and_visible(self) -> None:
        self.assertEqual(self.queue.issue_codes(), tuple(sorted(self.queue.issue_codes())))
        self.assertIn("missing_required_field", self.queue.issue_codes())
        self.assertIn("contradiction_unresolved", self.queue.issue_codes())
        self.assertEqual(len(self.queue.issue_codes()), 13)

    def test_serialized_summary_contains_counts(self) -> None:
        body = self.queue.to_dict()
        self.assertTrue(body["accepted"])
        self.assertEqual(body["ready_count"], 4)
        self.assertEqual(body["blocked_count"], 12)
        self.assertEqual(body["next_item_id"], self.queue.next_item().item_id)

    def test_contract_registry_remains_independent_of_queue(self) -> None:
        contracts = default_evidence_lifecycle_contracts()
        self.assertEqual(len(contracts.contracts), 4)
        self.assertGreaterEqual(len(contracts.issue_codes()), len(self.queue.issue_codes()))

    def test_positive_issue_rows_are_still_accepted_when_expected(self) -> None:
        citation = next(item for item in self.queue.items if item.record_id == "C01-POS-001")
        disagreement = next(item for item in self.queue.items if item.record_id == "C04-POS-001")
        self.assertTrue(citation.accepted)
        self.assertTrue(disagreement.accepted)
        self.assertTrue(citation.issue_codes)
        self.assertTrue(disagreement.issue_codes)

    def test_controls_retain_execution_issue_codes(self) -> None:
        for item in self.queue.blocked_items:
            self.assertEqual(item.issue_codes, self.evaluation.execution_map()[item.record_id].issue_codes)


if __name__ == "__main__":
    unittest.main()
