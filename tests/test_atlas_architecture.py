"""Focused contract, adapter, lineage, and release tests for D05."""

from __future__ import annotations

import unittest

from glio_noncode.atlas_architecture_access import atlas_architecture_access_policy
from glio_noncode.atlas_architecture_contracts import (
    ATLAS_ARCHITECTURE_CASE_COUNT,
    ATLAS_ARCHITECTURE_CONTEXT,
    AtlasArchitectureScenario,
    AtlasArchitectureState,
)
from glio_noncode.atlas_architecture_depth import atlas_architecture_depth_report
from glio_noncode.atlas_architecture_failures import classify_atlas_architecture_failures
from glio_noncode.atlas_architecture_invariants import check_atlas_architecture_invariants
from glio_noncode.atlas_architecture_lineage import build_atlas_architecture_ledger
from glio_noncode.atlas_architecture_metrics import materialize_atlas_architecture_metrics
from glio_noncode.atlas_architecture_operations import (
    evaluate_atlas_architecture_fixture,
    execute_atlas_architecture_case,
)
from glio_noncode.atlas_architecture_plan import compile_atlas_architecture_plan
from glio_noncode.atlas_architecture_policy import score_atlas_architecture_policy
from glio_noncode.atlas_architecture_public_data import (
    audit_atlas_architecture_data,
    default_atlas_architecture_fixture,
)
from glio_noncode.atlas_architecture_quality import assess_atlas_architecture_quality
from glio_noncode.atlas_architecture_replay import replay_atlas_architecture_fixture
from glio_noncode.atlas_architecture_review import build_atlas_architecture_review_queue
from glio_noncode.atlas_architecture_runtime import run_atlas_architecture
from glio_noncode.atlas_architecture_schema import atlas_architecture_schema
from glio_noncode.atlas_architecture_validation import validate_atlas_architecture_matrix


class AtlasArchitectureFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_atlas_architecture_fixture()
        cls.evaluation = evaluate_atlas_architecture_fixture(cls.fixture)

    def test_cardinality_context_sources_and_audit(self) -> None:
        self.assertEqual(self.fixture.context_key, ATLAS_ARCHITECTURE_CONTEXT)
        self.assertEqual(len(self.fixture.sources), 20)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), ATLAS_ARCHITECTURE_CASE_COUNT)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        report = audit_atlas_architecture_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 16)
        self.assertTrue(all(item.public_aggregate for item in self.fixture.sources))
        self.assertTrue(all(item.delegate_context_key for item in self.fixture.cases))
        self.assertTrue(all(item.content_address for item in report.checks))

    def test_operations_are_four_scenario_contracts(self) -> None:
        for operation in self.fixture.operation_ids:
            cases = [item for item in self.fixture.cases if item.operation.value == operation]
            self.assertEqual(len(cases), 4)
            self.assertEqual(
                {item.scenario for item in cases},
                {
                    AtlasArchitectureScenario.POSITIVE,
                    AtlasArchitectureScenario.FOREIGN_CONTEXT,
                    AtlasArchitectureScenario.MALFORMED_INPUT,
                    AtlasArchitectureScenario.IDENTITY_CONFLICT,
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
            if item.expected_state is AtlasArchitectureState.REVIEW
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
            all(item.observed_state is AtlasArchitectureState.REVIEW for item in controls)
        )

    def test_direct_policy_and_case_execution(self) -> None:
        report = score_atlas_architecture_policy(self.fixture.fixture_id, self.fixture.cases)
        self.assertTrue(report.accepted)
        case = next(
            item
            for item in self.fixture.cases
            if item.scenario is AtlasArchitectureScenario.FOREIGN_CONTEXT
        )
        execution = execute_atlas_architecture_case(case, self.fixture.context_key)
        self.assertEqual(execution.observed_state, AtlasArchitectureState.REVIEW)
        self.assertEqual(execution.issue_codes, ("context_mismatch",))
        self.assertEqual(execution.observed_result_state, "out_of_domain")


class AtlasArchitectureRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_atlas_architecture_fixture()
        cls.runtime = run_atlas_architecture(cls.fixture, run_id="test-atlas-runtime")

    def test_published_runtime_depth(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.state, AtlasArchitectureState.PUBLISHED)
        self.assertEqual(len(self.runtime.stages), 24)
        self.assertEqual(tuple(item.ordinal for item in self.runtime.stages), tuple(range(1, 25)))
        self.assertEqual(len(self.runtime.artifacts), 6)
        self.assertTrue(self.runtime.compliance.accepted)
        self.assertEqual(self.runtime.depth.check_count, 458)
        self.assertEqual(len(self.runtime.quality.checks), 12)

    def test_plan_matrix_review_and_lineage(self) -> None:
        evaluation = self.runtime.evaluation
        plan = compile_atlas_architecture_plan(self.fixture)
        matrix = validate_atlas_architecture_matrix(self.fixture, evaluation)
        queue = build_atlas_architecture_review_queue(self.fixture.fixture_id, self.fixture.cases)
        ledger = build_atlas_architecture_ledger(
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
        validation = validate_atlas_architecture_matrix(self.fixture, evaluation)
        metrics = materialize_atlas_architecture_metrics(
            self.fixture, evaluation, queue, len(validation)
        )
        self.assertEqual(metrics.case_count, 64)
        self.assertEqual(metrics.control_issue_count, 48)
        self.assertEqual(metrics.positive_issue_count, 0)
        self.assertTrue(atlas_architecture_access_policy(self.runtime.artifacts).checks[0].passed)
        quality = assess_atlas_architecture_quality(
            self.fixture,
            evaluation,
            self.runtime.plan,
            queue,
            self.runtime.ledger,
            self.runtime.artifacts,
            self.runtime.release,
            24,
        )
        depth = atlas_architecture_depth_report(
            self.fixture, evaluation, self.runtime.plan, queue, self.runtime.ledger, self.runtime
        )
        self.assertTrue(quality.passed)
        self.assertTrue(depth.accepted)
        self.assertEqual(depth.addressed_count, 228)
        self.assertEqual(depth.family_count, 4)
        self.assertEqual(depth.check_count, 458)
        self.assertEqual(depth.state_count, 6)

    def test_replay_schema_failures_and_invariants(self) -> None:
        replay = replay_atlas_architecture_fixture(self.fixture, self.runtime.evaluation)
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.first_address, replay.second_address)
        self.assertTrue(all(item.passed for item in atlas_architecture_schema().checks))
        self.assertFalse(
            classify_atlas_architecture_failures(self.runtime.evaluation).release_blocked
        )
        invariants = check_atlas_architecture_invariants(
            self.fixture,
            self.runtime.evaluation,
            self.runtime.plan,
            self.runtime.review_queue,
            self.runtime.ledger,
        )
        self.assertTrue(all(item.passed for item in invariants))


if __name__ == "__main__":
    unittest.main()
