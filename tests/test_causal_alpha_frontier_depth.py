from __future__ import annotations

import unittest

from glio_noncode.causal_alpha_frontier_adapters import build_causal_alpha_frontier_adapters
from glio_noncode.causal_alpha_frontier_contracts import build_causal_alpha_frontier_contracts
from glio_noncode.causal_alpha_frontier_depth import audit_causal_alpha_frontier_depth
from glio_noncode.causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from glio_noncode.causal_alpha_frontier_lineage import build_causal_alpha_frontier_lineage
from glio_noncode.causal_alpha_frontier_metrics import build_causal_alpha_frontier_metrics
from glio_noncode.causal_alpha_frontier_provenance import build_causal_alpha_frontier_provenance
from glio_noncode.causal_alpha_frontier_public_data import default_causal_alpha_frontier_fixture
from glio_noncode.causal_alpha_frontier_schema import validate_causal_alpha_frontier_schema
from glio_noncode.causal_alpha_frontier_scenario_matrix import build_causal_alpha_frontier_scenario_matrix
from glio_noncode.causal_alpha_frontier_validation_matrix import build_causal_alpha_frontier_validation_matrix
from glio_noncode.causal_alpha_frontier_runtime import run_causal_alpha_frontier_runtime


class CausalAlphaFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_alpha_frontier_fixture()
        self.evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        self.contracts = build_causal_alpha_frontier_contracts()
        self.schema = validate_causal_alpha_frontier_schema(self.fixture, self.evaluation.evaluation, self.contracts)
        self.metrics = build_causal_alpha_frontier_metrics(self.fixture, self.evaluation)
        self.adapters = build_causal_alpha_frontier_adapters()
        self.lineage = build_causal_alpha_frontier_lineage(self.fixture, self.evaluation)
        self.provenance = build_causal_alpha_frontier_provenance(self.fixture, self.evaluation, self.lineage)

    def test_depth_audit_is_accepted(self) -> None:
        depth = audit_causal_alpha_frontier_depth(self.fixture, self.evaluation, self.adapters, self.contracts, self.schema, self.metrics, self.lineage, self.provenance)
        self.assertTrue(depth.accepted)
        self.assertEqual(depth.failed_checks, ())
        self.assertEqual(len(depth.checks), 8)

    def test_depth_audit_lists_all_implementation_planes(self) -> None:
        depth = audit_causal_alpha_frontier_depth(self.fixture, self.evaluation, self.adapters, self.contracts, self.schema, self.metrics, self.lineage, self.provenance)
        self.assertEqual(depth.implementation_modules, (
            "glio_noncode.causal_alpha_frontier_public_data",
            "glio_noncode.causal_alpha_frontier_adapters",
            "glio_noncode.causal_alpha_frontier_fixture_eval",
            "glio_noncode.causal_alpha_frontier_contracts",
            "glio_noncode.causal_alpha_frontier_schema",
            "glio_noncode.causal_alpha_frontier_metrics",
            "glio_noncode.causal_alpha_frontier_policy",
            "glio_noncode.causal_alpha_frontier_lineage",
            "glio_noncode.causal_alpha_frontier_provenance",
            "glio_noncode.causal_alpha_frontier_runtime",
        ))
        self.assertTrue(all(item.startswith("tests.test_causal_alpha_frontier_") for item in depth.test_modules))

    def test_schema_checks_have_addressed_check_rows(self) -> None:
        self.assertTrue(self.schema.accepted)
        self.assertEqual(self.schema.failed_checks, ())
        self.assertEqual(len(self.schema.checks), 7)
        self.assertTrue(all(item["content_address"].startswith("sha256:") for item in self.schema.checks))

    def test_scenario_matrix_classifies_exact_and_foreign_context(self) -> None:
        matrix = build_causal_alpha_frontier_scenario_matrix(self.fixture, self.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(sum(item.context_class == "foreign" for item in matrix.scenarios), 4)
        self.assertEqual(sum(item.context_class == "exact" for item in matrix.scenarios), 12)
        self.assertEqual(sum(item.role == "positive" for item in matrix.scenarios), 4)

    def test_validation_matrix_has_capability_evidence(self) -> None:
        matrix = build_causal_alpha_frontier_validation_matrix(self.fixture.fixture_id, self.evaluation, self.contracts, self.metrics)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.cells), 4)
        self.assertEqual({item.capability_id for item in matrix.cells}, {"GNC-D11-C09", "GNC-D11-C10", "GNC-D11-C11", "GNC-D11-C12"})
        self.assertTrue(all(item.accepted_count == item.expected_count == 4 for item in matrix.cells))
        self.assertTrue(all(item.release_state == "verified" for item in matrix.cells))

    def test_runtime_stage_order_is_contiguous(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-stage-order")
        self.assertEqual(tuple(item.sequence for item in runtime.stages), tuple(range(1, 32)))
        self.assertEqual(runtime.stage_ids, (
            "data-audit", "adapters", "fixture-replay", "contracts", "schema", "metrics", "lineage", "provenance", "integrity", "depth-audit", "policy", "decisions", "reconciliation", "review-queue", "control-coverage", "decision-traces", "projections", "diagnostics", "scenario-matrix", "validation-matrix", "quality-gate", "release-bundle", "release-manifest", "artifact-inventory", "deterministic-replay", "operational-matrix", "claim-boundary", "review-view", "exports", "assurance", "runbook",
        ))

    def test_runtime_stage_addresses_are_closed(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-stage-addresses")
        self.assertTrue(all(item.output_address.startswith("sha256:") for item in runtime.stages))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in runtime.stages))
        self.assertEqual(len({item.content_address for item in runtime.stages}), 31)

    def test_provenance_contains_expected_node_kinds(self) -> None:
        kinds = {item.kind for item in self.provenance.nodes}
        self.assertEqual(kinds, {"fixture", "source", "record", "result"})
        self.assertEqual(sum(item.kind == "source" for item in self.provenance.nodes), 5)
        self.assertEqual(sum(item.kind == "record" for item in self.provenance.nodes), 16)
        self.assertEqual(sum(item.kind == "result" for item in self.provenance.nodes), 16)

    def test_lineage_edge_types_are_closed(self) -> None:
        self.assertEqual({edge[2] for edge in self.lineage.edges}, {"supplies", "evaluates"})
        self.assertEqual(sum(edge[2] == "supplies" for edge in self.lineage.edges), 25)
        self.assertEqual(sum(edge[2] == "evaluates" for edge in self.lineage.edges), 16)

    def test_metrics_expose_state_and_issue_counts(self) -> None:
        self.assertEqual(self.metrics.accepted_records, 16)
        for metric in self.metrics.operations:
            self.assertEqual(metric.record_count, 4)
            self.assertEqual(metric.accepted_count, 4)
            self.assertGreaterEqual(metric.issue_count, 1)
            self.assertEqual(metric.coverage_fraction, 1.0)


if __name__ == "__main__":
    unittest.main()
