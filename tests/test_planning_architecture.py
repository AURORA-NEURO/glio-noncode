"""D13 aggregate contract, delegate, and runtime tests."""

from __future__ import annotations

import unittest

from glio_noncode.planning_architecture_audit import deep_audit_planning_architecture
from glio_noncode.planning_architecture_compliance import assess_planning_architecture_compliance
from glio_noncode.planning_architecture_contract_matrix import planning_architecture_contract_matrix
from glio_noncode.planning_architecture_controls import planning_architecture_control_summary
from glio_noncode.planning_architecture_depth import assess_planning_architecture_depth
from glio_noncode.planning_architecture_ledger import (
    build_planning_architecture_ledger,
    planning_architecture_ledger_is_closed,
)
from glio_noncode.planning_architecture_operations import evaluate_planning_architecture_fixture
from glio_noncode.planning_architecture_plan import build_planning_architecture_plan
from glio_noncode.planning_architecture_public_data import (
    audit_planning_architecture_data,
    default_planning_architecture_fixture,
)
from glio_noncode.planning_architecture_release import build_planning_architecture_release
from glio_noncode.planning_architecture_replay import replay_planning_architecture_fixture
from glio_noncode.planning_architecture_review import build_planning_architecture_review_queue
from glio_noncode.planning_architecture_runtime import (
    PLANNING_ARCHITECTURE_STAGE_IDS,
    run_planning_architecture,
)


class PlanningArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_planning_architecture_fixture()
        cls.audit = audit_planning_architecture_data(cls.fixture)
        cls.evaluation = evaluate_planning_architecture_fixture(cls.fixture)

    def test_fixture_cardinality_and_audit(self) -> None:
        self.assertEqual(len(self.fixture.sources), 20)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertTrue(self.audit.accepted)

    def test_delegate_states_and_controls_are_retained(self) -> None:
        by_id = {item.case_id: item for item in self.evaluation.executions}
        self.assertEqual(by_id["D13-C01-POS-001"].observed_state.value, "ready")
        self.assertEqual(by_id["D13-C05-POS-001"].observed_state.value, "designed")
        self.assertEqual(by_id["D13-C09-POS-001"].observed_state.value, "ready_for_review")
        self.assertEqual(by_id["D13-C13-POS-001"].observed_state.value, "ready")
        self.assertIn("context_mismatch", by_id["D13-C01-CTRL-003"].observed_issue_codes)
        self.assertIn("mode_unsupported", by_id["D13-C05-CTRL-001"].observed_issue_codes)
        self.assertIn("invalid_guide_oligo_row", by_id["D13-C10-CTRL-002"].observed_issue_codes)
        self.assertIn("prerequisite_cycle", by_id["D13-C14-CTRL-002"].observed_issue_codes)

    def test_evaluation_receipts_and_check_depth(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 64)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 458)
        self.assertTrue(all(item.passed for item in self.evaluation.checks))

    def test_plan_review_lineage_ledger_and_release(self) -> None:
        plan = build_planning_architecture_plan(self.fixture)
        review = build_planning_architecture_review_queue(self.evaluation)
        ledger = build_planning_architecture_ledger(self.fixture, self.evaluation)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.nodes), 16)
        self.assertEqual(len(review.items), 48)
        self.assertTrue(planning_architecture_ledger_is_closed(ledger))
        self.assertEqual(len(ledger.events), 80)
        self.assertEqual(len(planning_architecture_contract_matrix(self.fixture)), 16)
        release = build_planning_architecture_release(self.fixture, self.evaluation, ())
        self.assertEqual(release.state.value, "review")

    def test_runtime_quality_depth_and_compliance(self) -> None:
        runtime = run_planning_architecture(self.fixture)
        depth = assess_planning_architecture_depth(self.fixture, self.evaluation)
        compliance = assess_planning_architecture_compliance(self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertTrue(runtime.quality.accepted)
        self.assertEqual(len(runtime.stages), 24)
        self.assertEqual(
            tuple(item.stage_id for item in runtime.stages), PLANNING_ARCHITECTURE_STAGE_IDS
        )
        self.assertEqual(depth.check_count, 458)
        self.assertTrue(compliance.accepted)
        self.assertEqual(planning_architecture_control_summary(self.fixture)["control_count"], 48)

    def test_replay_and_deep_audit(self) -> None:
        replay = replay_planning_architecture_fixture(self.fixture)
        audit = deep_audit_planning_architecture(self.fixture)
        self.assertTrue(replay.accepted)
        self.assertTrue(audit["accepted"])
        self.assertEqual(audit["schema_errors"], ())
        self.assertEqual(audit["lineage"]["gap_count"], 0)


if __name__ == "__main__":
    unittest.main()
