"""Focused contract, adapter, lineage, and release tests for D03."""

from __future__ import annotations

import unittest

from glio_noncode.specimen_architecture_access import specimen_architecture_access_policy
from glio_noncode.specimen_architecture_compliance import (
    assess_specimen_architecture_compliance,
)
from glio_noncode.specimen_architecture_contracts import (
    SPECIMEN_ARCHITECTURE_CASE_COUNT,
    SPECIMEN_ARCHITECTURE_CONTEXT,
    SpecimenArchitectureScenario,
    SpecimenArchitectureState,
)
from glio_noncode.specimen_architecture_depth import specimen_architecture_depth_report
from glio_noncode.specimen_architecture_failures import classify_specimen_architecture_failures
from glio_noncode.specimen_architecture_invariants import check_specimen_architecture_invariants
from glio_noncode.specimen_architecture_lineage import build_specimen_architecture_ledger
from glio_noncode.specimen_architecture_metrics import materialize_specimen_architecture_metrics
from glio_noncode.specimen_architecture_operations import (
    evaluate_specimen_architecture_fixture,
    execute_specimen_architecture_case,
)
from glio_noncode.specimen_architecture_plan import compile_specimen_architecture_plan
from glio_noncode.specimen_architecture_policy import score_specimen_architecture_policy
from glio_noncode.specimen_architecture_public_data import (
    audit_specimen_architecture_data,
    default_specimen_architecture_fixture,
)
from glio_noncode.specimen_architecture_quality import assess_specimen_architecture_quality
from glio_noncode.specimen_architecture_replay import replay_specimen_architecture_fixture
from glio_noncode.specimen_architecture_review import build_specimen_architecture_review_queue
from glio_noncode.specimen_architecture_runtime import run_specimen_architecture
from glio_noncode.specimen_architecture_schema import specimen_architecture_schema
from glio_noncode.specimen_architecture_validation import (
    validate_specimen_architecture_matrix,
)


class SpecimenArchitectureFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_specimen_architecture_fixture()
        cls.evaluation = evaluate_specimen_architecture_fixture(cls.fixture)

    def test_cardinality_and_context(self) -> None:
        self.assertEqual(self.fixture.context_key, SPECIMEN_ARCHITECTURE_CONTEXT)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), SPECIMEN_ARCHITECTURE_CASE_COUNT)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)

    def test_sources_and_audit(self) -> None:
        self.assertGreaterEqual(len(self.fixture.sources), 6)
        report = audit_specimen_architecture_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 15)
        self.assertTrue(all(item.content_address for item in report.checks))

    def test_operations_are_four_scenario_contracts(self) -> None:
        for operation in self.fixture.operation_ids:
            cases = [item for item in self.fixture.cases if item.operation.value == operation]
            self.assertEqual(len(cases), 4)
            self.assertEqual(
                {item.scenario for item in cases},
                {
                    SpecimenArchitectureScenario.POSITIVE,
                    SpecimenArchitectureScenario.FOREIGN_CONTEXT,
                    SpecimenArchitectureScenario.MALFORMED_INPUT,
                    SpecimenArchitectureScenario.IDENTITY_CONFLICT,
                },
            )

    def test_positive_and_controls_execute(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertTrue(all(item.passed for item in self.evaluation.receipts))
        self.assertEqual(self.evaluation.positive_count, 16)
        self.assertEqual(self.evaluation.control_count, 48)
        self.assertEqual(len(self.evaluation.checks), 458)

    def test_controls_are_conservative(self) -> None:
        controls = [
            item
            for item in self.evaluation.receipts
            if item.expected_state is SpecimenArchitectureState.REVIEW
        ]
        self.assertEqual(
            {item.observed_result_state for item in controls},
            {"out_of_domain", "invalid", "contradictory"},
        )
        self.assertEqual(
            {code for item in controls for code in item.observed_issue_codes},
            {"context_mismatch", "malformed_input", "identity_conflict"},
        )

    def test_direct_policy_and_case_execution(self) -> None:
        report = score_specimen_architecture_policy(self.fixture.fixture_id, self.fixture.cases)
        self.assertTrue(report.accepted)
        case = next(
            item
            for item in self.fixture.cases
            if item.scenario is SpecimenArchitectureScenario.FOREIGN_CONTEXT
        )
        execution = execute_specimen_architecture_case(case, self.fixture.context_key)
        self.assertEqual(execution.observed_state, SpecimenArchitectureState.REVIEW)
        self.assertEqual(execution.issue_codes, ("context_mismatch",))


class SpecimenArchitectureRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_specimen_architecture_fixture()
        cls.runtime = run_specimen_architecture(cls.fixture, run_id="test-specimen-runtime")

    def test_published_runtime_depth(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.state, SpecimenArchitectureState.PUBLISHED)
        self.assertEqual(len(self.runtime.stages), 24)
        self.assertEqual(tuple(item.ordinal for item in self.runtime.stages), tuple(range(1, 25)))
        self.assertEqual(len(self.runtime.artifacts), 6)
        self.assertEqual(self.runtime.depth.check_count, 458)
        self.assertTrue(self.runtime.compliance.accepted)

    def test_plan_matrix_review_and_lineage(self) -> None:
        evaluation = self.runtime.evaluation
        plan = compile_specimen_architecture_plan(self.fixture)
        matrix = validate_specimen_architecture_matrix(self.fixture, evaluation)
        queue = build_specimen_architecture_review_queue(
            self.fixture.fixture_id, self.fixture.cases
        )
        ledger = build_specimen_architecture_ledger(
            self.fixture.fixture_id, self.fixture.cases, evaluation
        )
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.nodes), 16)
        self.assertEqual(len(matrix), 112)
        self.assertTrue(all(item.passed for item in matrix))
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.items), 48)
        self.assertTrue(ledger.accepted)
        self.assertEqual(len(ledger.events), 64)

    def test_metrics_access_quality_and_depth(self) -> None:
        queue = self.runtime.review_queue
        evaluation = self.runtime.evaluation
        validation = validate_specimen_architecture_matrix(self.fixture, evaluation)
        metrics = materialize_specimen_architecture_metrics(
            self.fixture, evaluation, queue, len(validation)
        )
        self.assertEqual(metrics.case_count, 64)
        self.assertEqual(metrics.source_count, 15)
        self.assertEqual(metrics.check_count, 458)
        self.assertEqual(metrics.state_count, 6)
        self.assertEqual(metrics.issue_code_count, 3)
        self.assertEqual(metrics.issue_count, 48)
        self.assertTrue(
            specimen_architecture_access_policy(self.runtime.artifacts).checks[0].passed
        )
        quality = assess_specimen_architecture_quality(
            self.fixture,
            evaluation,
            self.runtime.plan,
            queue,
            self.runtime.ledger,
            self.runtime.artifacts,
            self.runtime.release,
            24,
            self.runtime.compliance,
        )
        depth = specimen_architecture_depth_report(
            self.fixture, evaluation, self.runtime.plan, queue, self.runtime.ledger, self.runtime
        )
        self.assertTrue(quality.passed)
        self.assertTrue(depth.accepted)
        self.assertEqual(depth.addressed_count, 223)
        self.assertEqual(len(assess_specimen_architecture_compliance(self.fixture).checks), 8)

    def test_replay_schema_failures_and_invariants(self) -> None:
        replay = replay_specimen_architecture_fixture(self.fixture, self.runtime.evaluation)
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.first_address, replay.second_address)
        self.assertTrue(all(item.passed for item in specimen_architecture_schema().checks))
        self.assertFalse(
            classify_specimen_architecture_failures(self.runtime.evaluation).release_blocked
        )
        invariants = check_specimen_architecture_invariants(
            self.fixture,
            self.runtime.evaluation,
            self.runtime.plan,
            self.runtime.review_queue,
            self.runtime.ledger,
        )
        self.assertTrue(all(item.passed for item in invariants))


if __name__ == "__main__":
    unittest.main()
