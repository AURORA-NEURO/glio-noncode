"""Focused contract tests for the Domain 12 C05-C08 release plane."""

from __future__ import annotations

import unittest
import json

from glio_noncode.cohort_beta import CohortBetaState, RegulatoryRecurrenceTester
from glio_noncode.cohort_beta_frontier_adapters import default_cohort_beta_frontier_adapters, validate_cohort_beta_frontier_payload
from glio_noncode.cohort_beta_frontier_claim_boundary import build_cohort_beta_frontier_claim_boundary
from glio_noncode.cohort_beta_frontier_contracts import default_cohort_beta_frontier_contracts
from glio_noncode.cohort_beta_frontier_depth import audit_cohort_beta_frontier_depth
from glio_noncode.cohort_beta_frontier_exports import export_cohort_beta_frontier_review_csv, render_cohort_beta_frontier_review_markdown
from glio_noncode.cohort_beta_frontier_fixture_eval import evaluate_cohort_beta_frontier_fixture
from glio_noncode.cohort_beta_frontier_metrics import measure_cohort_beta_frontier
from glio_noncode.cohort_beta_frontier_policy import CohortBetaFrontierDisposition, materialize_cohort_beta_frontier_policy
from glio_noncode.cohort_beta_frontier_public_data import C05_C08_CONTEXT, audit_cohort_beta_frontier_data, default_cohort_beta_frontier_fixture
from glio_noncode.cohort_beta_frontier_quality_gate import evaluate_cohort_beta_frontier_quality
from glio_noncode.cohort_beta_frontier_reconciliation import reconcile_cohort_beta_frontier
from glio_noncode.cohort_beta_frontier_replay import replay_cohort_beta_frontier, replay_is_deterministic
from glio_noncode.cohort_beta_frontier_review import build_cohort_beta_frontier_review_queue
from glio_noncode.cohort_beta_frontier_runtime import run_cohort_beta_frontier_runtime
from glio_noncode.cohort_beta_frontier_schema import default_cohort_beta_frontier_schema, validate_cohort_beta_frontier_schema
from glio_noncode.cohort_beta_frontier_views import build_cohort_beta_frontier_review_view


class CohortBetaFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_cohort_beta_frontier_fixture()
        cls.evaluation = evaluate_cohort_beta_frontier_fixture(cls.fixture)
        cls.contracts = default_cohort_beta_frontier_contracts()
        cls.policy = materialize_cohort_beta_frontier_policy(cls.evaluation, cls.contracts)
        cls.reconciliation = reconcile_cohort_beta_frontier(cls.fixture, cls.evaluation, cls.policy)

    def test_fixture_is_closed_public_aggregate_boundary(self) -> None:
        audit = audit_cohort_beta_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.record_count, 16)
        self.assertEqual(audit.foreign_context_count, 4)
        self.assertEqual(audit.operation_counts, {"C05": 4, "C06": 4, "C07": 4, "C08": 4})

    def test_all_four_operations_reconcile_expected_states(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(self.evaluation.supported_count, 4)
        self.assertEqual(self.evaluation.control_count, 12)
        self.assertEqual(self.evaluation.mismatch_count, 0)
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual({row.operation for row in self.evaluation.rows}, {"C05", "C06", "C07", "C08"})

    def test_expected_state_distribution_is_explicit(self) -> None:
        states = {state: sum(row.observed_state is state for row in self.evaluation.rows) for state in CohortBetaState}
        self.assertEqual(states[ CohortBetaState.SUPPORTED], 4)
        self.assertEqual(states[CohortBetaState.ABSENT], 3)
        self.assertEqual(states[CohortBetaState.PARTIAL], 4)
        self.assertEqual(states[CohortBetaState.OUT_OF_DOMAIN], 4)
        self.assertEqual(states[CohortBetaState.CONTRADICTORY], 1)

    def test_policy_publishes_only_supported_rows(self) -> None:
        self.assertEqual(self.policy.publishable_count, 4)
        self.assertEqual(self.policy.review_count, 4)
        self.assertEqual(self.policy.quarantine_count, 8)
        self.assertTrue(all(item.disposition is CohortBetaFrontierDisposition.PUBLISH for item in self.policy.decisions if item.state is CohortBetaState.SUPPORTED))

    def test_schema_and_adapter_contracts(self) -> None:
        schema = default_cohort_beta_frontier_schema()
        self.assertTrue(validate_cohort_beta_frontier_schema(schema))
        adapters = default_cohort_beta_frontier_adapters()
        self.assertEqual(len(adapters.specs), 4)
        self.assertTrue(validate_cohort_beta_frontier_payload("C05", {"observations": ()}, adapters).accepted)
        self.assertFalse(validate_cohort_beta_frontier_payload("C06", {"observations": ()}, adapters).accepted)

    def test_quality_replay_depth_and_views(self) -> None:
        from glio_noncode.cohort_beta_frontier_lineage import build_cohort_beta_frontier_lineage

        metrics = measure_cohort_beta_frontier(self.evaluation)
        lineage = build_cohort_beta_frontier_lineage(self.fixture, self.evaluation)
        quality = evaluate_cohort_beta_frontier_quality(self.fixture, self.evaluation, self.contracts, default_cohort_beta_frontier_schema(), lineage, self.reconciliation)
        replay = replay_cohort_beta_frontier(self.fixture)
        depth = audit_cohort_beta_frontier_depth(self.fixture, self.evaluation, metrics, lineage, quality)
        view = build_cohort_beta_frontier_review_view(self.evaluation, self.policy, C05_C08_CONTEXT)
        queue = build_cohort_beta_frontier_review_queue(self.evaluation, self.policy)
        self.assertTrue(quality.accepted)
        self.assertTrue(replay_is_deterministic(replay))
        self.assertTrue(depth.accepted)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(queue.items), 12)
        self.assertIn("# C05-C08 review queue", render_cohort_beta_frontier_review_markdown(queue))
        self.assertEqual(export_cohort_beta_frontier_review_csv(queue).splitlines()[0], "record_id,operation,priority,disposition,reason")

    def test_runtime_has_ordered_depth(self) -> None:
        report = run_cohort_beta_frontier_runtime()
        self.assertTrue(report.accepted)
        self.assertGreaterEqual(len(report.stages), 35)
        self.assertEqual(tuple(stage.ordinal for stage in report.stages), tuple(range(1, len(report.stages) + 1)))
        self.assertTrue(report.release.ready)
        self.assertTrue(report.assurance.accepted)
        self.assertEqual(report.claim_evidence.claims[0].operation, "C05")

    def test_runtime_projection_is_json_serializable(self) -> None:
        report = run_cohort_beta_frontier_runtime()
        payload = json.dumps(report.to_dict(), sort_keys=True)
        self.assertIn('"accepted": true', payload)

    def test_recurrence_primitive_remains_exact_context(self) -> None:
        result = RegulatoryRecurrenceTester().test(({"record_id": "r", "variant_id": "v", "sample_id": "s", "chromosome": "chr7", "position": 100, "context_key": "other", "source_id": "public", "source_version": "v1"},), context_key=C05_C08_CONTEXT)
        self.assertEqual(result.state, CohortBetaState.OUT_OF_DOMAIN)


if __name__ == "__main__":
    unittest.main()
