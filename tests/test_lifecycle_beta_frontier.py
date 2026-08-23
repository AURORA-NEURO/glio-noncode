from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.lifecycle_beta_frontier_adapters import (
    build_lifecycle_beta_frontier_adapters,
    execute_lifecycle_beta_frontier_record_with_adapter,
)
from glio_noncode.lifecycle_beta_frontier_artifacts import build_lifecycle_beta_frontier_artifact_inventory
from glio_noncode.lifecycle_beta_frontier_bundle import assemble_lifecycle_beta_frontier_bundle
from glio_noncode.lifecycle_beta_frontier_contracts import (
    LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY,
    LifecycleBetaFrontierOperation,
    LifecycleBetaFrontierRole,
    LifecycleBetaFrontierState,
)
from glio_noncode.lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_handoff import (
    build_lifecycle_beta_frontier_handoff,
    validate_lifecycle_beta_frontier_handoff,
)
from glio_noncode.lifecycle_beta_frontier_lineage import (
    build_lifecycle_beta_frontier_lineage,
    verify_lifecycle_beta_frontier_lineage,
)
from glio_noncode.lifecycle_beta_frontier_metrics import measure_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_policy import (
    default_lifecycle_beta_frontier_policy,
    evaluate_lifecycle_beta_frontier_policy,
)
from glio_noncode.lifecycle_beta_frontier_public_data import (
    audit_lifecycle_beta_frontier_data,
    default_lifecycle_beta_frontier_fixture,
)
from glio_noncode.lifecycle_beta_frontier_quality_gate import run_lifecycle_beta_frontier_quality_gate
from glio_noncode.lifecycle_beta_frontier_reconciliation import reconcile_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_release import build_lifecycle_beta_frontier_release
from glio_noncode.lifecycle_beta_frontier_replay import replay_lifecycle_beta_frontier_evaluation
from glio_noncode.lifecycle_beta_frontier_review_queue import build_lifecycle_beta_frontier_review_queue
from glio_noncode.lifecycle_beta_frontier_schema import (
    default_lifecycle_beta_frontier_schema,
    validate_lifecycle_beta_frontier_schema,
)
from glio_noncode.lifecycle_beta_frontier_views import (
    build_lifecycle_beta_frontier_view,
    filter_lifecycle_beta_frontier_review_queue,
)


class LifecycleBetaFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_lifecycle_beta_frontier_fixture()
        self.audit = audit_lifecycle_beta_frontier_data(self.fixture)
        self.evaluation = evaluate_lifecycle_beta_frontier_fixture(self.fixture)
        self.metrics = measure_lifecycle_beta_frontier(self.evaluation)
        self.adapters = build_lifecycle_beta_frontier_adapters()
        self.schema = default_lifecycle_beta_frontier_schema()
        self.policy = default_lifecycle_beta_frontier_policy()
        self.lineage = build_lifecycle_beta_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_lifecycle_beta_frontier(self.fixture, self.evaluation)
        self.quality = run_lifecycle_beta_frontier_quality_gate(
            self.fixture,
            self.audit,
            self.evaluation,
            self.metrics,
            self.adapters,
            self.schema,
            self.policy,
            self.lineage,
            self.reconciliation,
        )
        self.replay = replay_lifecycle_beta_frontier_evaluation(self.fixture, self.evaluation)
        self.release = build_lifecycle_beta_frontier_release(
            self.fixture,
            self.evaluation,
            self.quality,
            self.lineage,
            self.replay,
        )
        self.artifacts = build_lifecycle_beta_frontier_artifact_inventory(self.fixture, self.release)
        self.view = build_lifecycle_beta_frontier_view(self.evaluation)
        self.queue = build_lifecycle_beta_frontier_review_queue(self.evaluation)
        self.handoff = build_lifecycle_beta_frontier_handoff(
            self.fixture, self.evaluation, self.metrics
        )

    def test_public_boundary_and_counts(self) -> None:
        self.assertEqual(self.fixture.context_key, LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.sources), 9)
        self.assertEqual(len(self.fixture.records), 32)
        self.assertEqual(len(self.fixture.positive_records), 8)
        self.assertEqual(len(self.fixture.control_records), 24)
        self.assertTrue(self.audit.accepted)

    def test_each_operation_has_one_positive_and_three_controls(self) -> None:
        for operation in LifecycleBetaFrontierOperation:
            rows = self.fixture.by_operation(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role is LifecycleBetaFrontierRole.POSITIVE for item in rows), 1)
            self.assertEqual(sum(item.role is LifecycleBetaFrontierRole.CONTROL for item in rows), 3)

    def test_all_operations_execute(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 32)
        self.assertEqual(self.evaluation.failed_check_ids, ())
        self.assertEqual(self.evaluation.passed_checks, 166)

    def test_positive_rows_are_accepted(self) -> None:
        self.assertEqual(sum(item.accepted for item in self.evaluation.executions), 8)
        for item in self.evaluation.executions:
            if item.role is LifecycleBetaFrontierRole.POSITIVE:
                self.assertTrue(item.accepted, item.record_id)

    def test_control_rows_preserve_non_success_states(self) -> None:
        controls = tuple(item for item in self.evaluation.executions if item.role is LifecycleBetaFrontierRole.CONTROL)
        self.assertEqual(len(controls), 24)
        self.assertTrue(all(not item.accepted for item in controls))
        self.assertIn(LifecycleBetaFrontierState.OUT_OF_DOMAIN, {item.state for item in controls})
        self.assertIn(LifecycleBetaFrontierState.PARTIAL, {item.state for item in controls})
        self.assertIn(LifecycleBetaFrontierState.ABSTAINED, {item.state for item in controls})

    def test_operation_states_are_distinct_and_expected(self) -> None:
        expected = {
            "C05-POS-001": LifecycleBetaFrontierState.SUPPORTED,
            "C06-POS-001": LifecycleBetaFrontierState.SUPPORTED,
            "C07-POS-001": LifecycleBetaFrontierState.SUPPORTED,
            "C08-POS-001": LifecycleBetaFrontierState.CONTRADICTORY,
            "C09-POS-001": LifecycleBetaFrontierState.ADJUDICATED,
            "C10-POS-001": LifecycleBetaFrontierState.READY_FOR_REVIEW,
            "C11-POS-001": LifecycleBetaFrontierState.APPROVED,
            "C12-POS-001": LifecycleBetaFrontierState.REVIEW_REQUIRED,
        }
        observed = {item.record_id: item.state for item in self.evaluation.executions}
        for record_id, state in expected.items():
            self.assertIs(observed[record_id], state)

    def test_every_execution_has_output_and_address(self) -> None:
        for item in self.evaluation.executions:
            self.assertTrue(item.output)
            self.assertTrue(item.content_address.startswith("sha256:"))

    def test_adapter_registry_has_eight_complete_specs(self) -> None:
        self.assertEqual(len(self.adapters.specs), 8)
        self.assertEqual({item.operation for item in self.adapters.specs}, set(LifecycleBetaFrontierOperation))
        self.assertTrue(all(item.deterministic for item in self.adapters.specs))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.adapters.specs))

    def test_adapter_execution_matches_direct_execution(self) -> None:
        for record in self.fixture.records:
            result = execute_lifecycle_beta_frontier_record_with_adapter(record, self.adapters)
            direct = next(item for item in self.evaluation.executions if item.record_id == record.record_id)
            self.assertEqual(result.execution.content_address, direct.content_address)
            self.assertEqual(result.adapter_operation, record.operation)

    def test_metrics_conserve_records(self) -> None:
        self.assertEqual(self.metrics.record_count, 32)
        self.assertEqual(self.metrics.positive_count, 8)
        self.assertEqual(self.metrics.control_count, 24)
        self.assertEqual(self.metrics.accepted_count, 8)
        for operation in LifecycleBetaFrontierOperation:
            metric = self.metrics.by_operation(operation)
            self.assertEqual(metric.record_count, 4)
            self.assertEqual(metric.positive_count, 1)
            self.assertEqual(metric.control_count, 3)
            self.assertEqual(metric.accepted_count, 1)

    def test_schema_is_complete(self) -> None:
        self.assertTrue(validate_lifecycle_beta_frontier_schema(self.schema))
        self.assertEqual(len(self.schema.fields), 8)
        self.assertEqual(len(self.schema.operations), 8)
        self.assertTrue(self.schema.content_address.startswith("sha256:"))

    def test_policy_has_disjoint_use_sets(self) -> None:
        self.assertTrue(set(self.policy.allowed_uses).isdisjoint(self.policy.excluded_uses))
        check = evaluate_lifecycle_beta_frontier_policy(LifecycleBetaFrontierState.REVIEW_REQUIRED, self.policy)
        self.assertFalse(check.allowed)
        self.assertTrue(check.content_address.startswith("sha256:"))

    def test_lineage_is_closed(self) -> None:
        self.assertTrue(verify_lifecycle_beta_frontier_lineage(self.lineage))
        self.assertEqual(len(self.lineage.source_ids), 9)
        self.assertEqual(len(self.lineage.execution_ids), 32)
        self.assertGreaterEqual(len(self.lineage.edges), 32)

    def test_reconciliation_is_accepted(self) -> None:
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.reconciliation.failed_record_ids, ())
        self.assertEqual(len(self.reconciliation.items), 32)

    def test_quality_gate_is_blocking_and_green(self) -> None:
        self.assertTrue(self.quality.accepted)
        self.assertEqual(self.quality.failed_check_ids, ())
        self.assertEqual(len(self.quality.checks), 8)
        self.assertTrue(all(item.blocking for item in self.quality.checks))

    def test_replay_is_deterministic(self) -> None:
        self.assertTrue(self.replay.deterministic)
        self.assertEqual(len(self.replay.checks), 32)
        self.assertTrue(all(item.passed for item in self.replay.checks))

    def test_release_and_artifacts_are_closed(self) -> None:
        self.assertTrue(self.release.accepted)
        self.assertTrue(self.release.research_use_only)
        self.assertTrue(self.artifacts.complete)
        self.assertEqual(len(self.artifacts.artifacts), 5)

    def test_view_and_queue_conserve_rows(self) -> None:
        self.assertEqual(len(self.view.entries), 32)
        self.assertEqual(len(self.queue.items), 32)
        self.assertEqual(len(filter_lifecycle_beta_frontier_review_queue(self.view, include_controls=False)), 8)
        self.assertTrue(self.queue.items[0].priority >= self.queue.items[-1].priority)

    def test_handoff_is_reproducible(self) -> None:
        self.assertTrue(validate_lifecycle_beta_frontier_handoff(self.handoff))
        self.assertEqual(self.handoff.operation_count, 8)
        self.assertEqual(self.handoff.record_count, 32)
        self.assertEqual(len(self.handoff.source_ids), 9)
        for operation in LifecycleBetaFrontierOperation:
            item = self.handoff.item(operation)
            self.assertEqual(item.record_count, 4)
            self.assertEqual(item.positive_count, 1)
            self.assertEqual(item.control_count, 3)
            self.assertEqual(item.accepted_count, 1)

    def test_mutated_reconciliation_is_not_green(self) -> None:
        mutated = replace(self.reconciliation, reconciled=False, failed_record_ids=("C05-POS-001",))
        self.assertFalse(mutated.reconciled)
        self.assertIn("C05-POS-001", mutated.failed_record_ids)

    def test_mutated_quality_is_not_green(self) -> None:
        mutated = replace(self.quality, accepted=False, failed_check_ids=("evaluation",))
        self.assertFalse(mutated.accepted)

    def test_root_exports_are_available(self) -> None:
        import glio_noncode

        self.assertTrue(hasattr(glio_noncode, "run_lifecycle_beta_frontier_runtime"))
        self.assertTrue(hasattr(glio_noncode, "build_lifecycle_beta_frontier_threshold_report"))
        self.assertTrue(hasattr(glio_noncode, "LifecycleBetaFrontierOperation"))


if __name__ == "__main__":
    unittest.main()
