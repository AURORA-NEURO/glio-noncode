from __future__ import annotations

import unittest

from glio_noncode.topology_beta_frontier_benchmark import build_topology_beta_frontier_benchmark
from glio_noncode.topology_beta_frontier_claim_boundary import build_topology_beta_frontier_claim_boundary
from glio_noncode.topology_beta_frontier_composite import build_topology_beta_frontier_composite, summarize_topology_beta_frontier_composite
from glio_noncode.topology_beta_frontier_conformance import build_topology_beta_frontier_conformance
from glio_noncode.topology_beta_frontier_evidence_matrix import build_topology_beta_frontier_evidence_matrix, summarize_topology_beta_frontier_evidence_matrix
from glio_noncode.topology_beta_frontier_failure_catalog import build_topology_beta_frontier_failure_catalog, classify_topology_beta_frontier_issues
from glio_noncode.topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_inspection import build_topology_beta_frontier_inspection, summarize_topology_beta_frontier_inspection
from glio_noncode.topology_beta_frontier_pipeline import run_topology_beta_frontier_pipeline
from glio_noncode.topology_beta_frontier_public_data import default_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_queries import TopologyBetaFrontierQuery, query_topology_beta_frontier, query_topology_beta_frontier_summary
from glio_noncode.topology_beta_frontier_replay_ledger import build_topology_beta_frontier_replay_ledger, compare_topology_beta_frontier_ledgers
from glio_noncode.topology_beta_frontier_source_checks import build_topology_beta_frontier_source_checks
from glio_noncode.topology_beta_frontier_source_registry import build_topology_beta_frontier_source_registry


class TopologyBetaFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_beta_frontier_fixture()
        self.evaluation = evaluate_topology_beta_frontier_fixture(self.fixture)

    def test_evidence_matrix_is_complete(self) -> None:
        matrix = build_topology_beta_frontier_evidence_matrix(self.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(matrix.operation_count, 4)
        self.assertEqual(matrix.record_count, 16)
        self.assertEqual(matrix.review_count, 12)
        self.assertEqual(summarize_topology_beta_frontier_evidence_matrix(matrix)["states"]["supported"], 4)

    def test_claim_boundary_has_allowed_and_blocked_statements(self) -> None:
        report = build_topology_beta_frontier_claim_boundary(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.allowed_count, 16)
        self.assertEqual(report.blocked_count, 16)
        self.assertIn("bounded score", report.for_operation("enhancer_promoter_contact")[0].allowed_statement)

    def test_failure_catalog_covers_every_observed_issue(self) -> None:
        catalog = build_topology_beta_frontier_failure_catalog(self.evaluation)
        self.assertTrue(catalog.accepted)
        self.assertIn("context_mismatch", catalog.observed_codes)
        self.assertIn("missingness", classify_topology_beta_frontier_issues(catalog))
        self.assertEqual(catalog.for_code("missing_activity").state_effect, "abstained")

    def test_conformance_preserves_declared_missingness(self) -> None:
        report = build_topology_beta_frontier_conformance(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 16)
        partial = next(item for item in report.checks if item.record_id == "D09-C06-C1")
        self.assertIn("bait_id", partial.missing_fields)
        self.assertTrue(partial.passed)

    def test_source_receipt_checks_are_closed(self) -> None:
        registry = build_topology_beta_frontier_source_registry(self.fixture)
        report = build_topology_beta_frontier_source_checks(self.fixture, registry)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 24)
        self.assertEqual(report.failed(), ())

    def test_benchmark_has_four_bounded_cases(self) -> None:
        report = build_topology_beta_frontier_benchmark(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.cases), 4)
        self.assertEqual(report.total_records, 16)
        self.assertEqual(report.for_operation("loop_stripe").record_count, 4)

    def test_composite_view_keeps_operation_outputs_separate(self) -> None:
        report = build_topology_beta_frontier_composite(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.links), 4)
        self.assertTrue(all(len(item.operation_ids) == 4 for item in report.links))
        self.assertEqual(summarize_topology_beta_frontier_composite(report)["link_count"], 4)

    def test_query_filters_are_deterministic(self) -> None:
        supported = query_topology_beta_frontier(self.evaluation, TopologyBetaFrontierQuery(state="supported"))
        controls = query_topology_beta_frontier(self.evaluation, TopologyBetaFrontierQuery(role="control"))
        foreign = query_topology_beta_frontier(self.evaluation, TopologyBetaFrontierQuery(issue_code="context_mismatch"))
        self.assertTrue(supported.accepted)
        self.assertEqual(supported.count, 4)
        self.assertEqual(controls.count, 12)
        self.assertEqual(foreign.count, 4)
        self.assertEqual(query_topology_beta_frontier_summary(self.evaluation)["record_count"], 16)

    def test_inspection_view_exposes_next_actions(self) -> None:
        report = build_topology_beta_frontier_inspection(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.filter(role="positive")), 4)
        self.assertEqual(len(report.filter(state="out_of_domain")), 4)
        self.assertEqual(summarize_topology_beta_frontier_inspection(report)["row_count"], 16)
        self.assertTrue(all(item.next_action for item in report.rows))

    def test_replay_ledger_has_ordered_stage_receipts(self) -> None:
        first = build_topology_beta_frontier_replay_ledger(run_topology_beta_frontier_pipeline(self.fixture))
        second = build_topology_beta_frontier_replay_ledger(run_topology_beta_frontier_pipeline(self.fixture))
        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(len(first.entries), 12)
        self.assertEqual(first.entry("evaluation").sequence, 4)
        comparison = compare_topology_beta_frontier_ledgers(first, second)
        self.assertTrue(comparison["same_stages"])
        self.assertTrue(comparison["accepted"])


if __name__ == "__main__":
    unittest.main()
