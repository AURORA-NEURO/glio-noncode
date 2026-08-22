"""Depth and invariant tests for the Domain 11 evidence frontier."""

from __future__ import annotations

import unittest

from glio_noncode.causal_frontier_contracts import default_causal_frontier_contracts
from glio_noncode.causal_frontier_depth import audit_causal_frontier_depth
from glio_noncode.causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from glio_noncode.causal_frontier_lineage import build_causal_frontier_lineage
from glio_noncode.causal_frontier_metrics import measure_causal_frontier
from glio_noncode.causal_frontier_policy import default_causal_frontier_policy
from glio_noncode.causal_frontier_public_data import (
    CausalFrontierOperation,
    default_causal_frontier_fixture,
)
from glio_noncode.causal_frontier_quality_gate import evaluate_causal_frontier_quality
from glio_noncode.causal_frontier_reconciliation import reconcile_causal_frontier
from glio_noncode.causal_frontier_runtime import run_causal_frontier_runtime
from glio_noncode.causal_frontier_schema import default_causal_frontier_schema


class CausalFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_frontier_fixture()
        self.evaluation = evaluate_causal_frontier_fixture(self.fixture)
        self.contracts = default_causal_frontier_contracts()
        self.schema = default_causal_frontier_schema()
        self.policy = default_causal_frontier_policy(self.contracts)
        self.lineage = build_causal_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_causal_frontier(self.fixture, self.evaluation, self.policy)
        self.gate = evaluate_causal_frontier_quality(
            self.fixture,
            self.evaluation,
            self.contracts,
            self.schema,
            self.lineage,
            self.reconciliation,
        )

    def test_depth_audit_passes_all_eighteen_checks(self) -> None:
        audit = audit_causal_frontier_depth()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 18)
        self.assertEqual(audit.passed_count, 18)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertTrue(audit.content_address)

    def test_depth_audit_serialization_contains_summary(self) -> None:
        payload = audit_causal_frontier_depth().to_dict()
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_count"], 18)
        self.assertEqual(payload["failed_check_ids"], [])
        self.assertEqual(len(payload["checks"]), 18)

    def test_depth_has_expected_count_checks(self) -> None:
        checks = {item.check_id: item for item in audit_causal_frontier_depth().checks}
        expected = {
            "source-count": 5,
            "record-count": 16,
            "positive-count": 4,
            "control-count": 12,
            "operation-count": 4,
            "schema-count": 4,
            "evaluation-check-count": 120,
            "lineage-edge-count": 36,
            "quality-check-count": 12,
            "runtime-stage-count": 10,
            "metric-count": 13,
        }
        for check_id, value in expected.items():
            self.assertTrue(checks[check_id].passed, check_id)
            self.assertEqual(checks[check_id].observed, value)

    def test_depth_has_expected_boolean_checks(self) -> None:
        checks = {item.check_id: item for item in audit_causal_frontier_depth().checks}
        for check_id in (
            "data-audit",
            "evaluation",
            "reconciliation",
            "quality-gate",
            "runtime",
            "replay",
            "determinism",
        ):
            self.assertTrue(checks[check_id].passed, check_id)
            self.assertIs(checks[check_id].observed, True)

    def test_lineage_edges_are_more_detailed_than_record_count(self) -> None:
        self.assertEqual(len(self.lineage.edges), 36)
        source_edges = tuple(item for item in self.lineage.edges if item.edge_kind == "source_to_execution")
        fixture_edges = tuple(item for item in self.lineage.edges if item.edge_kind == "fixture_to_execution")
        self.assertEqual(len(source_edges), 20)
        self.assertEqual(len(fixture_edges), 16)
        self.assertTrue(self.lineage.acyclic)

    def test_quality_gate_has_one_check_per_boundary(self) -> None:
        check_ids = {item.check_id for item in self.gate.checks}
        self.assertEqual(
            check_ids,
            {
                "data-audit",
                "evaluation",
                "contract-coverage",
                "schema-coverage",
                "lineage-acyclic",
                "lineage-terminals",
                "reconciliation",
                "content-addresses",
                "source-boundary",
                "positive-controls",
                "negative-controls",
                "issue-vocabulary",
            },
        )
        self.assertTrue(all(item.passed for item in self.gate.checks))

    def test_runtime_stages_are_strictly_ordered(self) -> None:
        runtime = run_causal_frontier_runtime(self.fixture, run_id="ordered-runtime")
        self.assertEqual([item.sequence for item in runtime.stages], list(range(1, 11)))
        self.assertEqual(len(set(item.output_address for item in runtime.stages)), 10)
        self.assertTrue(all(item.duration_ms >= 0 for item in runtime.stages))

    def test_operation_reports_are_four_by_four(self) -> None:
        for operation in CausalFrontierOperation:
            executions = self.evaluation.by_operation(operation)
            self.assertEqual(len(executions), 4)
            self.assertEqual(sum(item.accepted for item in executions), 1)
            self.assertEqual(sum(bool(item.issue_codes) for item in executions), 3)

    def test_metric_addresses_are_present(self) -> None:
        report = measure_causal_frontier(self.evaluation)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in report.metrics))
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_contract_and_schema_addresses_are_present(self) -> None:
        self.assertTrue(self.contracts.content_address.startswith("sha256:"))
        self.assertTrue(self.schema.content_address.startswith("sha256:"))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.contracts.contracts))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.schema.operations))

    def test_policy_decision_count_matches_operation_count(self) -> None:
        decisions = self.policy.decide(self.evaluation)
        self.assertEqual(len(decisions), len(CausalFrontierOperation))
        self.assertEqual({item.operation for item in decisions}, set(CausalFrontierOperation))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in decisions))


if __name__ == "__main__":
    unittest.main()
