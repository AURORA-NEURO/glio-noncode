"""Comprehensive tests for the D11 causal evidence research aggregate."""

from __future__ import annotations

import unittest

from glio_noncode.causal_architecture_audit import deep_audit_causal_architecture
from glio_noncode.causal_architecture_compliance import assess_causal_architecture_compliance
from glio_noncode.causal_architecture_contract_matrix import (
    build_causal_architecture_contract_matrix,
    causal_architecture_contract_matrix_is_closed,
    causal_architecture_contract_matrix_summary,
)
from glio_noncode.causal_architecture_controls import (
    causal_architecture_control_coverage,
    causal_architecture_controls_are_closed,
)
from glio_noncode.causal_architecture_depth import (
    assess_causal_architecture_depth,
    causal_architecture_depth_percent,
)
from glio_noncode.causal_architecture_ledger import (
    build_causal_architecture_ledger,
    causal_architecture_ledger_is_closed,
)
from glio_noncode.causal_architecture_lineage import (
    build_causal_architecture_lineage,
    causal_architecture_lineage_gaps,
)
from glio_noncode.causal_architecture_metrics import (
    causal_architecture_metric_invariants,
    causal_architecture_metrics,
)
from glio_noncode.causal_architecture_operations import evaluate_causal_architecture_fixture
from glio_noncode.causal_architecture_plan import (
    build_causal_architecture_plan,
    causal_architecture_operation_order,
)
from glio_noncode.causal_architecture_public_data import (
    audit_causal_architecture_data,
    default_causal_architecture_fixture,
)
from glio_noncode.causal_architecture_query import query_causal_architecture_cases
from glio_noncode.causal_architecture_replay import replay_causal_architecture_fixture
from glio_noncode.causal_architecture_review import build_causal_architecture_review_queue
from glio_noncode.causal_architecture_runtime import run_causal_architecture
from glio_noncode.causal_architecture_schema import (
    causal_architecture_schema_descriptor,
    validate_causal_architecture_fixture,
)


class CausalArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_causal_architecture_fixture()
        cls.evaluation = evaluate_causal_architecture_fixture(cls.fixture)

    def test_fixture_cardinality_and_four_family_balance(self) -> None:
        self.assertEqual(len(self.fixture.sources), 20)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertEqual(len({item.family for item in self.fixture.operations}), 4)

    def test_data_audit_and_schema_close(self) -> None:
        audit = audit_causal_architecture_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(tuple(item.check_id for item in audit.checks if not item.passed), ())
        self.assertTrue(validate_causal_architecture_fixture(self.fixture))
        self.assertEqual(causal_architecture_schema_descriptor()["source_count"], 20)

    def test_family_results_are_retained(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 458)
        positive = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "accepted"
        }
        self.assertEqual(len(positive), 16)
        self.assertEqual(positive["D11-C01-positive"].observed_result_state, "supported")
        self.assertEqual(positive["D11-C05-positive"].observed_result_state, "supported")
        self.assertEqual(positive["D11-C12-positive"].observed_result_state, "partial")
        self.assertEqual(positive["D11-C16-positive"].observed_result_state, "published")

    def test_controls_preserve_issue_vocabulary(self) -> None:
        controls = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value == "review"
        }
        self.assertEqual(len(controls), 48)
        self.assertEqual(
            controls["D11-C01-control_c"].observed_issue_codes,
            ("context_mismatch",),
        )
        self.assertEqual(
            controls["D11-C05-control_a"].observed_issue_codes,
            ("minimum_independent_sources",),
        )
        self.assertEqual(
            controls["D11-C09-control_c"].observed_issue_codes,
            ("context_mismatch",),
        )
        self.assertEqual(
            controls["D11-C16-control_a"].observed_issue_codes,
            ("invalid_dossier_input",),
        )

    def test_plan_review_lineage_ledger_and_metrics_close(self) -> None:
        plan = build_causal_architecture_plan(self.fixture)
        review = build_causal_architecture_review_queue(self.evaluation)
        lineage = build_causal_architecture_lineage(self.fixture)
        ledger = build_causal_architecture_ledger(self.fixture, self.evaluation)
        metrics = causal_architecture_metrics(self.fixture, self.evaluation)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(causal_architecture_operation_order(plan)), 16)
        self.assertEqual(len(review.items), 48)
        self.assertEqual(sum(len(value) for value in lineage["operation_cases"].values()), 64)
        self.assertEqual(causal_architecture_lineage_gaps(self.fixture), ())
        self.assertTrue(causal_architecture_ledger_is_closed(ledger))
        self.assertEqual(metrics["receipt_pass_rate"], 1.0)
        self.assertEqual(causal_architecture_metric_invariants(metrics), ())

    def test_runtime_release_depth_compliance_and_replay_close(self) -> None:
        runtime = run_causal_architecture(self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 24)
        self.assertEqual(len(runtime.artifacts), 6)
        self.assertEqual(runtime.release.state.value, "published")
        self.assertEqual(runtime.stages[-1].stage_id, "runtime-finalized")
        self.assertEqual(runtime.depth.check_count, 458)
        self.assertGreaterEqual(runtime.depth.state_count, 2)
        self.assertGreaterEqual(runtime.depth.issue_code_count, 15)
        self.assertEqual(len(runtime.quality.checks), 10)
        self.assertTrue(runtime.quality.accepted)
        self.assertTrue(replay_causal_architecture_fixture(self.fixture).accepted)
        self.assertTrue(assess_causal_architecture_compliance(self.fixture)["accepted"])
        self.assertEqual(
            causal_architecture_depth_percent(
                assess_causal_architecture_depth(self.fixture, self.evaluation)
            ),
            100.0,
        )

    def test_query_matrix_controls_and_deep_audit_close(self) -> None:
        runtime = run_causal_architecture(self.fixture)
        self.assertEqual(len(query_causal_architecture_cases(runtime, operation_id="D11-C13")), 4)
        matrix = build_causal_architecture_contract_matrix(self.fixture)
        self.assertTrue(causal_architecture_contract_matrix_is_closed(self.fixture))
        self.assertEqual(causal_architecture_contract_matrix_summary(matrix)["operation_count"], 16)
        self.assertTrue(causal_architecture_controls_are_closed(self.fixture, self.evaluation))
        self.assertEqual(
            causal_architecture_control_coverage(self.fixture, self.evaluation)["held_paths"],
            48,
        )
        self.assertTrue(all(deep_audit_causal_architecture(self.fixture)["checks"].values()))


if __name__ == "__main__":
    unittest.main()
