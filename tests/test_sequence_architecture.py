"""Focused contract, family delegation, lineage, and release tests for D06."""

from __future__ import annotations

import unittest

from glio_noncode.sequence_architecture_access import sequence_architecture_access_policy
from glio_noncode.sequence_architecture_contracts import (
    SEQUENCE_ARCHITECTURE_CASE_COUNT,
    SEQUENCE_ARCHITECTURE_CONTEXT,
    SequenceArchitectureScenario,
    SequenceArchitectureState,
)
from glio_noncode.sequence_architecture_depth import sequence_architecture_depth_report
from glio_noncode.sequence_architecture_failures import classify_sequence_architecture_failures
from glio_noncode.sequence_architecture_invariants import check_sequence_architecture_invariants
from glio_noncode.sequence_architecture_lineage import build_sequence_architecture_ledger
from glio_noncode.sequence_architecture_metrics import materialize_sequence_architecture_metrics
from glio_noncode.sequence_architecture_operations import (
    evaluate_sequence_architecture_fixture,
    execute_sequence_architecture_case,
)
from glio_noncode.sequence_architecture_plan import compile_sequence_architecture_plan
from glio_noncode.sequence_architecture_policy import score_sequence_architecture_policy
from glio_noncode.sequence_architecture_public_data import (
    audit_sequence_architecture_data,
    default_sequence_architecture_fixture,
)
from glio_noncode.sequence_architecture_quality import assess_sequence_architecture_quality
from glio_noncode.sequence_architecture_replay import replay_sequence_architecture_fixture
from glio_noncode.sequence_architecture_review import build_sequence_architecture_review_queue
from glio_noncode.sequence_architecture_runtime import run_sequence_architecture
from glio_noncode.sequence_architecture_schema import sequence_architecture_schema
from glio_noncode.sequence_architecture_validation import validate_sequence_architecture_matrix


class SequenceArchitectureFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_sequence_architecture_fixture()
        cls.evaluation = evaluate_sequence_architecture_fixture(cls.fixture)

    def test_cardinality_context_sources_and_audit(self) -> None:
        self.assertEqual(self.fixture.context_key, SEQUENCE_ARCHITECTURE_CONTEXT)
        self.assertEqual(len(self.fixture.sources), 17)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), SEQUENCE_ARCHITECTURE_CASE_COUNT)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        report = audit_sequence_architecture_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 13)
        self.assertTrue(all(item.content_address for item in report.checks))

    def test_operations_are_four_scenario_contracts(self) -> None:
        for operation in self.fixture.operation_ids:
            cases = [item for item in self.fixture.cases if item.operation_id == operation]
            self.assertEqual(len(cases), 4)
            self.assertEqual(
                {item.scenario for item in cases},
                {
                    SequenceArchitectureScenario.POSITIVE,
                    SequenceArchitectureScenario.FOREIGN_CONTEXT,
                    SequenceArchitectureScenario.MALFORMED_INPUT,
                    SequenceArchitectureScenario.IDENTITY_CONFLICT,
                },
            )

    def test_positive_and_controls_execute(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertTrue(all(item.passed for item in self.evaluation.receipts))
        self.assertEqual(self.evaluation.positive_count, 16)
        self.assertEqual(self.evaluation.control_count, 48)
        self.assertEqual(len(self.evaluation.checks), 325)

    def test_controls_are_conservative(self) -> None:
        controls = [
            item
            for item in self.evaluation.receipts
            if item.expected_state is SequenceArchitectureState.REVIEW
        ]
        self.assertEqual(
            {item.observed_result_state for item in controls},
            {"out_of_domain", "invalid", "contradictory"},
        )
        self.assertEqual(
            {code for item in controls for code in item.observed_issue_codes},
            {"context_mismatch", "malformed_input", "identity_conflict"},
        )
        self.assertTrue(
            all(item.observed_state is SequenceArchitectureState.REVIEW for item in controls)
        )

    def test_direct_policy_and_case_execution(self) -> None:
        report = score_sequence_architecture_policy(self.fixture.fixture_id, self.fixture.cases)
        self.assertTrue(report.accepted)
        case = next(
            item
            for item in self.fixture.cases
            if item.scenario is SequenceArchitectureScenario.FOREIGN_CONTEXT
        )
        execution = execute_sequence_architecture_case(case, self.fixture.context_key)
        self.assertEqual(execution.observed_state, SequenceArchitectureState.REVIEW)
        self.assertEqual(execution.issue_codes, ("context_mismatch",))
        self.assertEqual(execution.observed_result_state, "out_of_domain")


class SequenceArchitectureRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_sequence_architecture_fixture()
        cls.runtime = run_sequence_architecture(cls.fixture, run_id="test-sequence-runtime")

    def test_published_runtime_depth(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.state, SequenceArchitectureState.PUBLISHED)
        self.assertEqual(len(self.runtime.stages), 20)
        self.assertEqual(tuple(item.ordinal for item in self.runtime.stages), tuple(range(1, 21)))
        self.assertEqual(len(self.runtime.artifacts), 6)

    def test_plan_matrix_review_and_lineage(self) -> None:
        evaluation = self.runtime.evaluation
        plan = compile_sequence_architecture_plan(self.fixture)
        matrix = validate_sequence_architecture_matrix(self.fixture, evaluation)
        queue = build_sequence_architecture_review_queue(
            self.fixture.fixture_id, self.fixture.cases
        )
        ledger = build_sequence_architecture_ledger(
            self.fixture.fixture_id, self.fixture.cases, evaluation
        )
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.nodes), 16)
        self.assertEqual(len(matrix), 80)
        self.assertTrue(all(item.passed for item in matrix))
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.items), 48)
        self.assertTrue(ledger.accepted)
        self.assertEqual(len(ledger.events), 64)

    def test_metrics_access_quality_and_depth(self) -> None:
        queue = self.runtime.review_queue
        evaluation = self.runtime.evaluation
        validation = validate_sequence_architecture_matrix(self.fixture, evaluation)
        metrics = materialize_sequence_architecture_metrics(
            self.fixture, evaluation, queue, len(validation)
        )
        self.assertEqual(metrics.case_count, 64)
        self.assertEqual(metrics.control_issue_count, 48)
        self.assertGreater(metrics.positive_issue_count, 0)
        self.assertTrue(sequence_architecture_access_policy(self.runtime.artifacts).accepted)
        quality = assess_sequence_architecture_quality(
            self.fixture,
            evaluation,
            self.runtime.plan,
            queue,
            self.runtime.ledger,
            self.runtime.artifacts,
            self.runtime.release,
            20,
        )
        depth = sequence_architecture_depth_report(
            self.fixture, evaluation, self.runtime.plan, queue, self.runtime.ledger, self.runtime
        )
        self.assertTrue(quality.passed)
        self.assertTrue(depth.accepted)
        self.assertEqual(depth.addressed_count, 225)

    def test_replay_schema_failures_and_invariants(self) -> None:
        replay = replay_sequence_architecture_fixture(self.fixture, self.runtime.evaluation)
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.first_address, replay.second_address)
        self.assertTrue(all(item.passed for item in sequence_architecture_schema().checks))
        self.assertFalse(
            classify_sequence_architecture_failures(self.runtime.evaluation).release_blocked
        )
        invariants = check_sequence_architecture_invariants(
            self.fixture,
            self.runtime.evaluation,
            self.runtime.plan,
            self.runtime.review_queue,
            self.runtime.ledger,
        )
        self.assertTrue(all(item.passed for item in invariants))


if __name__ == "__main__":
    unittest.main()
