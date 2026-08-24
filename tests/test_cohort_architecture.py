"""Comprehensive tests for the D12 cohort architecture aggregate."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_architecture_audit import deep_audit_cohort_architecture
from glio_noncode.cohort_architecture_compliance import assess_cohort_architecture_compliance
from glio_noncode.cohort_architecture_contract_matrix import (
    build_cohort_architecture_contract_matrix,
    cohort_architecture_contract_matrix_is_closed,
    cohort_architecture_contract_matrix_summary,
)
from glio_noncode.cohort_architecture_controls import (
    cohort_architecture_control_coverage,
    cohort_architecture_controls_are_closed,
)
from glio_noncode.cohort_architecture_depth import (
    assess_cohort_architecture_depth,
    cohort_architecture_depth_percent,
)
from glio_noncode.cohort_architecture_ledger import (
    build_cohort_architecture_ledger,
    cohort_architecture_ledger_is_closed,
)
from glio_noncode.cohort_architecture_lineage import (
    build_cohort_architecture_lineage,
    cohort_architecture_lineage_gaps,
)
from glio_noncode.cohort_architecture_metrics import (
    cohort_architecture_metric_invariants,
    cohort_architecture_metrics,
)
from glio_noncode.cohort_architecture_operations import evaluate_cohort_architecture_fixture
from glio_noncode.cohort_architecture_plan import (
    build_cohort_architecture_plan,
    cohort_architecture_operation_order,
)
from glio_noncode.cohort_architecture_public_data import (
    audit_cohort_architecture_data,
    default_cohort_architecture_fixture,
)
from glio_noncode.cohort_architecture_query import query_cohort_architecture_cases
from glio_noncode.cohort_architecture_replay import replay_cohort_architecture_fixture
from glio_noncode.cohort_architecture_review import build_cohort_architecture_review_queue
from glio_noncode.cohort_architecture_runtime import run_cohort_architecture
from glio_noncode.cohort_architecture_schema import (
    cohort_architecture_schema_descriptor,
    validate_cohort_architecture_fixture,
)


class CohortArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_cohort_architecture_fixture()
        cls.evaluation = evaluate_cohort_architecture_fixture(cls.fixture)

    def test_fixture_cardinality_and_family_balance(self) -> None:
        self.assertEqual(len(self.fixture.sources), 22)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertEqual(len({item.family for item in self.fixture.operations}), 4)
        self.assertEqual(len(self.fixture.family_contexts), 4)

    def test_data_audit_and_schema_close(self) -> None:
        audit = audit_cohort_architecture_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(tuple(item.check_id for item in audit.checks if not item.passed), ())
        self.assertTrue(validate_cohort_architecture_fixture(self.fixture))
        self.assertEqual(cohort_architecture_schema_descriptor()["source_count"], 22)

    def test_real_family_results_are_retained(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 458)
        positive = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.expected_state.value in {"supported", "published"}
        }
        self.assertEqual(len(positive), 16)
        self.assertEqual(positive["D12-C01-positive"].observed_state.value, "supported")
        self.assertEqual(positive["D12-C05-positive"].observed_state.value, "supported")
        self.assertEqual(positive["D12-C12-positive"].observed_state.value, "supported")
        self.assertEqual(positive["D12-C16-positive"].observed_state.value, "published")

    def test_controls_preserve_family_state_and_issue_vocabulary(self) -> None:
        controls = {
            item.case_id: item
            for item in self.evaluation.receipts
            if item.case_id.endswith(("control_a", "control_b", "control_c"))
        }
        self.assertEqual(len(controls), 48)
        self.assertEqual(controls["D12-C01-control_b"].observed_state.value, "out_of_domain")
        self.assertEqual(
            controls["D12-C05-control_a"].observed_issue_codes,
            ("negative_control",),
        )
        self.assertEqual(
            controls["D12-C09-control_c"].observed_state.value,
            "abstained",
        )
        self.assertEqual(
            controls["D12-C13-control_a"].observed_issue_codes,
            ("parity_gap_high",),
        )
        self.assertEqual(
            controls["D12-C16-control_a"].observed_issue_codes,
            ("invalid_cohort_discovery_input",),
        )

    def test_plan_review_lineage_ledger_and_metrics_close(self) -> None:
        plan = build_cohort_architecture_plan(self.fixture)
        review = build_cohort_architecture_review_queue(self.evaluation)
        lineage = build_cohort_architecture_lineage(self.fixture)
        ledger = build_cohort_architecture_ledger(self.fixture, self.evaluation)
        metrics = cohort_architecture_metrics(self.fixture, self.evaluation)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(cohort_architecture_operation_order(plan)), 16)
        self.assertEqual(len(review.items), 48)
        self.assertEqual(sum(len(value) for value in lineage["operation_cases"].values()), 64)
        self.assertEqual(cohort_architecture_lineage_gaps(self.fixture), ())
        self.assertTrue(cohort_architecture_ledger_is_closed(ledger))
        self.assertEqual(metrics["receipt_pass_rate"], 1.0)
        self.assertEqual(cohort_architecture_metric_invariants(metrics), ())

    def test_runtime_release_depth_compliance_and_replay_close(self) -> None:
        runtime = run_cohort_architecture(self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 24)
        self.assertEqual(len(runtime.artifacts), 6)
        self.assertEqual(runtime.release.state.value, "published")
        self.assertEqual(runtime.stages[-1].stage_id, "runtime-finalized")
        self.assertEqual(runtime.depth.check_count, 458)
        self.assertGreaterEqual(runtime.depth.state_count, 8)
        self.assertGreaterEqual(runtime.depth.issue_code_count, 15)
        self.assertEqual(len(runtime.quality.checks), 12)
        self.assertTrue(runtime.quality.accepted)
        self.assertTrue(replay_cohort_architecture_fixture(self.fixture).accepted)
        self.assertTrue(assess_cohort_architecture_compliance(self.fixture)["accepted"])
        self.assertEqual(
            cohort_architecture_depth_percent(
                assess_cohort_architecture_depth(self.fixture, self.evaluation)
            ),
            100.0,
        )

    def test_query_matrix_controls_and_deep_audit_close(self) -> None:
        runtime = run_cohort_architecture(self.fixture)
        self.assertEqual(
            len(query_cohort_architecture_cases(runtime, operation_id="D12-C13")),
            4,
        )
        matrix = build_cohort_architecture_contract_matrix(self.fixture)
        self.assertTrue(cohort_architecture_contract_matrix_is_closed(self.fixture))
        self.assertEqual(
            cohort_architecture_contract_matrix_summary(matrix)["operation_count"],
            16,
        )
        self.assertTrue(cohort_architecture_controls_are_closed(self.fixture, self.evaluation))
        self.assertEqual(
            cohort_architecture_control_coverage(self.fixture, self.evaluation)["held_paths"],
            48,
        )
        self.assertTrue(all(deep_audit_cohort_architecture(self.fixture)["checks"].values()))


if __name__ == "__main__":
    unittest.main()
