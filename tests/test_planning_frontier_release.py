"""Release playbook, extended checks, and boundary tests."""

from __future__ import annotations

import unittest

from glio_noncode.planning_frontier_extended_checks import default_extended_check_definitions, evaluate_extended_checks
from glio_noncode.planning_frontier_fixture_eval import evaluate_planning_fixture
from glio_noncode.planning_frontier_playbook import default_planning_playbook
from glio_noncode.planning_frontier_public_data import default_planning_frontier_fixture
from glio_noncode.planning_frontier_release_checklist import build_planning_release_checklist
from glio_noncode.planning_frontier_research_boundary import audit_planning_boundary


class PlanningReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_planning_frontier_fixture()
        self.evaluation = evaluate_planning_fixture(self.fixture)

    def test_playbook_has_operation_and_release_guidance(self) -> None:
        playbook = default_planning_playbook()
        self.assertTrue(playbook.accepted)
        self.assertGreaterEqual(len(playbook.entries), 80)
        self.assertTrue(playbook.for_phase("eligibility"))
        self.assertTrue(playbook.for_phase("release"))

    def test_extended_checks_are_addressed(self) -> None:
        definitions = default_extended_check_definitions()
        results = evaluate_extended_checks(self.fixture, self.evaluation)
        self.assertGreaterEqual(len(definitions), 50)
        self.assertEqual(len(definitions), len(results))
        self.assertTrue(all(item.content_address.startswith("extended-check-result:") for item in results))
        self.assertTrue(all(item.passed for item in results))

    def test_release_checklist_and_claim_audit(self) -> None:
        checklist = build_planning_release_checklist(self.fixture, self.evaluation)
        boundary = audit_planning_boundary(self.fixture, self.evaluation)
        self.assertTrue(checklist.accepted)
        self.assertFalse(checklist.failed_checks)
        self.assertTrue(boundary.accepted)


if __name__ == "__main__":
    unittest.main()
