"""D16 platform execution architecture contract and runtime tests."""

from __future__ import annotations

import unittest

from glio_noncode.platform_execution_architecture_compliance import (
    assess_platform_execution_compliance,
)
from glio_noncode.platform_execution_architecture_depth import assess_platform_execution_depth
from glio_noncode.platform_execution_architecture_ledger import platform_execution_ledger_is_closed
from glio_noncode.platform_execution_architecture_matrix import platform_execution_contract_matrix
from glio_noncode.platform_execution_architecture_metrics import (
    platform_execution_metric_invariants,
    platform_execution_metrics,
)
from glio_noncode.platform_execution_architecture_operations import (
    evaluate_platform_execution_fixture,
)
from glio_noncode.platform_execution_architecture_plan import build_platform_execution_plan
from glio_noncode.platform_execution_architecture_public_data import (
    audit_platform_execution_data,
    default_platform_execution_fixture,
)
from glio_noncode.platform_execution_architecture_query import query_platform_execution
from glio_noncode.platform_execution_architecture_replay import replay_platform_execution_fixture
from glio_noncode.platform_execution_architecture_review import (
    build_platform_execution_review_queue,
)
from glio_noncode.platform_execution_architecture_runtime import (
    PLATFORM_EXECUTION_ARCHITECTURE_STAGE_IDS,
    run_platform_execution_architecture,
)
from glio_noncode.platform_execution_architecture_schema import (
    validate_platform_execution_fixture,
    validate_platform_execution_mapping,
)


class PlatformExecutionArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_platform_execution_fixture()
        cls.audit = audit_platform_execution_data(cls.fixture)
        cls.evaluation = evaluate_platform_execution_fixture(cls.fixture)
        cls.runtime = run_platform_execution_architecture(cls.fixture)

    def test_fixture_and_audit_shape(self) -> None:
        self.assertEqual(len(self.fixture.sources), 19)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertTrue(self.audit.accepted)
        self.assertEqual(validate_platform_execution_mapping(self.fixture.to_dict()), ())
        self.assertTrue(validate_platform_execution_fixture(self.fixture))

    def test_delegate_states_and_controls_are_retained(self) -> None:
        observed = {item.case_id: item for item in self.evaluation.executions}
        expected = {
            "D16-C01-POSITIVE-001": ("ready", ()),
            "D16-C01-CONTROL-A-001": ("abstained", ("no_roles_requested",)),
            "D16-C04-CONTROL-C-001": ("rejected", ("direct_identifier",)),
            "D16-C06-CONTROL-A-001": ("partial", ("capacity_exceeded",)),
            "D16-C07-CONTROL-B-001": ("abstained", ("no_eligible_candidate",)),
            "D16-C09-POSITIVE-001": ("completed", ()),
            "D16-C13-POSITIVE-001": ("ready", ()),
            "D16-C16-POSITIVE-001": ("released", ()),
        }
        for case_id, (state, issues) in expected.items():
            self.assertEqual(observed[case_id].observed_state.value, state)
            self.assertEqual(observed[case_id].observed_issue_codes, issues)

    def test_evaluation_receipts_and_check_depth(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 64)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 458)
        self.assertTrue(all(item.passed for item in self.evaluation.checks))

    def test_plan_review_ledger_replay_and_quality(self) -> None:
        plan = build_platform_execution_plan(self.fixture)
        review = build_platform_execution_review_queue(self.evaluation, self.fixture)
        replay = replay_platform_execution_fixture(self.fixture)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.nodes), 16)
        self.assertGreaterEqual(len(review.items), 48)
        self.assertTrue(platform_execution_ledger_is_closed(self.runtime.ledger))
        self.assertEqual(len(self.runtime.ledger.events), 80)
        self.assertTrue(replay.accepted)
        self.assertTrue(self.runtime.quality.accepted)
        self.assertTrue(self.runtime.quality.checks[-2].passed)

    def test_metrics_depth_release_and_stages(self) -> None:
        metrics = platform_execution_metrics(self.fixture, self.evaluation)
        depth = assess_platform_execution_depth(self.fixture, self.evaluation)
        self.assertEqual(platform_execution_metric_invariants(metrics), ())
        self.assertEqual(metrics["check_count"], 458)
        self.assertEqual(depth.case_count, 64)
        self.assertEqual(depth.issue_code_count, len(metrics["issue_counts"]))
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.release.state.value, "published")
        self.assertEqual(len(self.runtime.artifacts), 6)
        self.assertEqual(
            tuple(item.stage_id for item in self.runtime.stages),
            PLATFORM_EXECUTION_ARCHITECTURE_STAGE_IDS,
        )

    def test_boundary_matrix_query_and_coordination_closure(self) -> None:
        compliance = assess_platform_execution_compliance(self.fixture)
        matrix = platform_execution_contract_matrix(self.fixture)
        rows = query_platform_execution(
            fixture=self.fixture,
            evaluation=self.evaluation,
            operation="D16-C14",
        )
        self.assertTrue(compliance.accepted)
        self.assertEqual(compliance.forbidden_keys, ())
        self.assertEqual(len(matrix), 16)
        self.assertEqual(len(rows), 4)
        self.assertTrue(
            any(
                item.check_id == "quality:coordination-closure"
                for item in self.runtime.quality.checks
            )
        )


if __name__ == "__main__":
    unittest.main()
