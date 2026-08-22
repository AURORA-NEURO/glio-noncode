"""Depth tests for the Domain 13 validation-planning frontier."""

from __future__ import annotations

import unittest

from glio_noncode.validation_frontier_contracts import default_validation_frontier_contracts
from glio_noncode.validation_frontier_depth import audit_validation_frontier_depth
from glio_noncode.validation_frontier_fixture_eval import evaluate_validation_frontier_fixture
from glio_noncode.validation_frontier_lineage import build_validation_frontier_lineage
from glio_noncode.validation_frontier_metrics import measure_validation_frontier
from glio_noncode.validation_frontier_policy import default_validation_frontier_policy
from glio_noncode.validation_frontier_public_data import (
    ValidationFrontierOperation,
    default_validation_frontier_fixture,
)
from glio_noncode.validation_frontier_quality_gate import evaluate_validation_frontier_quality
from glio_noncode.validation_frontier_reconciliation import reconcile_validation_frontier
from glio_noncode.validation_frontier_runtime import run_validation_frontier_runtime
from glio_noncode.validation_frontier_schema import default_validation_frontier_schema


class ValidationFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_validation_frontier_fixture()
        self.evaluation = evaluate_validation_frontier_fixture(self.fixture)
        self.contracts = default_validation_frontier_contracts()
        self.schema = default_validation_frontier_schema()
        self.policy = default_validation_frontier_policy(self.contracts)
        self.lineage = build_validation_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_validation_frontier(self.fixture, self.evaluation, self.policy)
        self.gate = evaluate_validation_frontier_quality(self.fixture, self.evaluation, self.contracts, self.schema, self.lineage, self.reconciliation)

    def test_depth_audit_passes_all_twenty_checks(self) -> None:
        audit = audit_validation_frontier_depth()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 20)
        self.assertEqual(audit.passed_count, 20)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertTrue(audit.content_address.startswith("sha256:"))

    def test_depth_count_checks(self) -> None:
        checks = {item.check_id: item for item in audit_validation_frontier_depth().checks}
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
            "scenario-count": 31,
            "threshold-probe-count": 972,
        }
        for check_id, value in expected.items():
            self.assertTrue(checks[check_id].passed, check_id)
            self.assertEqual(checks[check_id].observed, value)

    def test_depth_boolean_checks(self) -> None:
        checks = {item.check_id: item for item in audit_validation_frontier_depth().checks}
        for check_id in ("data-audit", "evaluation", "reconciliation", "quality-gate", "runtime", "replay", "determinism"):
            self.assertTrue(checks[check_id].passed, check_id)
            self.assertIs(checks[check_id].observed, True)

    def test_lineage_has_source_and_fixture_edges(self) -> None:
        source_edges = tuple(item for item in self.lineage.edges if item.edge_kind == "source_to_execution")
        fixture_edges = tuple(item for item in self.lineage.edges if item.edge_kind == "fixture_to_execution")
        self.assertEqual(len(source_edges), 20)
        self.assertEqual(len(fixture_edges), 16)
        self.assertTrue(self.lineage.acyclic)

    def test_gate_ids_cover_all_boundaries(self) -> None:
        self.assertEqual({item.check_id for item in self.gate.checks}, {"data-audit", "evaluation", "contract-coverage", "schema-coverage", "lineage-acyclic", "lineage-terminals", "reconciliation", "addresses", "boundary", "positive-count", "control-count", "issue-vocabulary"})
        self.assertTrue(all(item.passed for item in self.gate.checks))

    def test_runtime_is_ordered_and_addressed(self) -> None:
        runtime = run_validation_frontier_runtime(self.fixture, run_id="ordered-validation-runtime")
        self.assertEqual([item.sequence for item in runtime.stages], list(range(1, 11)))
        self.assertEqual(len(set(item.output_address for item in runtime.stages)), 10)
        self.assertTrue(all(item.duration_ms >= 0 for item in runtime.stages))

    def test_operation_rows_are_four_by_four(self) -> None:
        for operation in ValidationFrontierOperation:
            values = self.evaluation.by_operation(operation)
            self.assertEqual(len(values), 4)
            self.assertEqual(sum(item.accepted for item in values), 1)
            self.assertEqual(sum(bool(item.issue_codes) for item in values), 3)

    def test_surface_addresses_exist(self) -> None:
        metrics = measure_validation_frontier(self.evaluation)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in metrics.metrics))
        self.assertTrue(self.contracts.content_address.startswith("sha256:"))
        self.assertTrue(self.schema.content_address.startswith("sha256:"))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.contracts.contracts))

    def test_policy_matches_operation_count(self) -> None:
        decisions = self.policy.decide(self.evaluation)
        self.assertEqual(len(decisions), len(ValidationFrontierOperation))
        self.assertEqual({item.operation for item in decisions}, set(ValidationFrontierOperation))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in decisions))


if __name__ == "__main__":
    unittest.main()
