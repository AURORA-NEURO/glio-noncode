from __future__ import annotations

import unittest

from glio_noncode.topology_frontier_exports import (
    export_topology_frontier_metrics_csv,
    export_topology_frontier_receipts_csv,
    export_topology_frontier_review_csv,
    render_topology_frontier_review_markdown,
)
from glio_noncode.topology_frontier_fixture_eval import evaluate_topology_frontier_fixture
from glio_noncode.topology_frontier_metrics import compute_topology_frontier_metrics
from glio_noncode.topology_frontier_observability import (
    build_topology_frontier_trace,
    compare_topology_frontier_runs,
)
from glio_noncode.topology_frontier_public_data import (
    TOPOLOGY_FRONTIER_CONTEXT_KEY,
    TopologyFrontierOperation,
    TopologyFrontierRole,
    audit_topology_frontier_data,
    default_topology_frontier_fixture,
)
from glio_noncode.topology_frontier_quality_gate import run_topology_frontier_quality_gate
from glio_noncode.topology_frontier_release import build_topology_frontier_release
from glio_noncode.topology_frontier_runtime import (
    TopologyFrontierRuntimeOptions,
    run_topology_frontier_pipeline,
)
from glio_noncode.topology_frontier_scenario_matrix import evaluate_topology_frontier_scenarios
from glio_noncode.topology_frontier_views import (
    build_topology_frontier_view,
    topology_frontier_review_summary,
)


class TopologyFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_frontier_fixture()
        self.evaluation = evaluate_topology_frontier_fixture(self.fixture)
        self.quality = run_topology_frontier_quality_gate(self.fixture)
        self.view = build_topology_frontier_view(self.fixture, self.evaluation)

    def test_fixture_has_exact_public_boundary(self) -> None:
        self.assertEqual(self.fixture.context_key, TOPOLOGY_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, "public_aggregate_non_patient")
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)

    def test_fixture_has_four_positive_and_twelve_controls(self) -> None:
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(all(item.role is TopologyFrontierRole.POSITIVE for item in self.fixture.positive_records))
        self.assertTrue(all(item.role is TopologyFrontierRole.CONTROL for item in self.fixture.control_records))

    def test_fixture_covers_all_operations(self) -> None:
        self.assertEqual({item.operation for item in self.fixture.records}, set(TopologyFrontierOperation))
        self.assertTrue(all(sum(item.operation is operation for item in self.fixture.records) == 4 for operation in TopologyFrontierOperation))

    def test_data_audit_is_accepted(self) -> None:
        report = audit_topology_frontier_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 9)
        self.assertEqual(report.failed_check_ids, ())

    def test_evaluation_is_accepted_with_120_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.receipts), 16)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())

    def test_positive_records_are_supported(self) -> None:
        positive = tuple(item for item in self.evaluation.receipts if item.role is TopologyFrontierRole.POSITIVE)
        self.assertEqual(len(positive), 4)
        self.assertTrue(all(item.adapter_state == "supported" for item in positive))

    def test_controls_remain_visible(self) -> None:
        controls = tuple(item for item in self.evaluation.receipts if item.role is TopologyFrontierRole.CONTROL)
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(item.adapter_state != "supported" for item in controls))
        self.assertTrue(any(item.adapter_state == "out_of_domain" for item in controls))
        self.assertTrue(any(item.adapter_state == "invalid" for item in controls))

    def test_each_operation_has_expected_positive_state(self) -> None:
        expected = {
            TopologyFrontierOperation.ECDNA_CONTACT: "supported",
            TopologyFrontierOperation.COMPARTMENT_SWITCH: "supported",
            TopologyFrontierOperation.TOPOLOGY_TRANSPORT: "supported",
            TopologyFrontierOperation.EVIDENCE_PUBLICATION: "supported",
        }
        for operation, state in expected.items():
            row = next(item for item in self.evaluation.receipts if item.operation is operation and item.role is TopologyFrontierRole.POSITIVE)
            self.assertEqual(row.adapter_state, state)

    def test_ecdna_controls_preserve_model_issue_codes(self) -> None:
        receipt = self.evaluation.receipts[1]
        self.assertIn("weak_ecDNA_contact", receipt.observed_issue_codes)
        self.assertIn("insufficient_ecDNA_sources", receipt.observed_issue_codes)

    def test_compartment_controls_preserve_stable_and_context_states(self) -> None:
        stable = self.evaluation.receipts[5]
        other_context = self.evaluation.receipts[6]
        self.assertEqual(stable.adapter_state, "partial")
        self.assertEqual(other_context.adapter_state, "out_of_domain")
        self.assertIn("context_mismatch", other_context.observed_issue_codes)

    def test_transport_controls_preserve_edge_issues(self) -> None:
        weak = self.evaluation.receipts[9]
        disconnected = self.evaluation.receipts[10]
        self.assertIn("weak_transported_signal", weak.observed_issue_codes)
        self.assertIn("topology_path_disconnected", disconnected.observed_issue_codes)

    def test_publication_controls_preserve_assay_and_empty_issues(self) -> None:
        no_assay = self.evaluation.receipts[14]
        empty = self.evaluation.receipts[15]
        self.assertIn("missing_assay_ids", no_assay.observed_issue_codes)
        self.assertIn("empty_3d_evidence", empty.observed_issue_codes)

    def test_receipts_are_sanitized_and_addressed(self) -> None:
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.evaluation.receipts))
        self.assertTrue(all("input_text" not in item.summary for item in self.evaluation.receipts))
        self.assertTrue(all("payload" not in item.summary for item in self.evaluation.receipts))

    def test_quality_gate_has_twelve_passing_checks(self) -> None:
        self.assertTrue(self.quality.accepted)
        self.assertEqual(len(self.quality.checks), 12)
        self.assertEqual(self.quality.failed_check_ids, ())
        self.assertTrue(self.quality.bundle.accepted)

    def test_metrics_cover_four_operations(self) -> None:
        metrics = compute_topology_frontier_metrics(self.evaluation)
        self.assertEqual(len(metrics.operation_metrics), 4)
        self.assertEqual(metrics.total_records, 16)
        self.assertEqual(metrics.total_positive, 4)
        self.assertEqual(metrics.total_controls, 12)
        self.assertEqual(metrics.total_supported, 4)
        self.assertEqual(metrics.total_review, 12)

    def test_scenario_matrix_is_accepted(self) -> None:
        report = evaluate_topology_frontier_scenarios(self.evaluation, fixture=self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.scenarios), 16)
        self.assertEqual(len(report.checks), 48)

    def test_view_has_twelve_review_rows_and_five_sources(self) -> None:
        self.assertTrue(self.view.accepted)
        self.assertEqual(self.view.review_count, 12)
        self.assertEqual(len(self.view.operation_views), 4)
        self.assertEqual(len(self.view.source_matrix), 5)
        self.assertEqual(len(self.view.accepted_record_ids), 4)

    def test_review_summary_counts_states(self) -> None:
        summary = topology_frontier_review_summary(self.view)
        self.assertEqual(summary["review_count"], 12)
        self.assertEqual(sum(count for _, count in summary["state_counts"]), 12)
        self.assertEqual(sum(count for _, count in summary["operation_counts"]), 12)

    def test_exports_have_expected_row_counts(self) -> None:
        receipts = export_topology_frontier_receipts_csv(self.evaluation)
        review = export_topology_frontier_review_csv(self.view)
        metrics = export_topology_frontier_metrics_csv(compute_topology_frontier_metrics(self.evaluation))
        markdown = render_topology_frontier_review_markdown(self.view)
        self.assertEqual(len(receipts.splitlines()), 17)
        self.assertEqual(len(review.splitlines()), 13)
        self.assertEqual(len(metrics.splitlines()), 5)
        self.assertIn("# Topology frontier review", markdown)
        self.assertIn("C13-CTRL-001", markdown)

    def test_release_manifest_is_accepted(self) -> None:
        release = build_topology_frontier_release(self.quality, run_id="d09-test", release_id="d09-release")
        self.assertEqual(release.release_state, "accepted")
        self.assertEqual(release.record_count, 16)
        self.assertEqual(release.positive_count, 4)
        self.assertEqual(release.control_count, 12)
        self.assertTrue(release.release_address.startswith("sha256:"))

    def test_runtime_trace_has_nine_stages(self) -> None:
        runtime = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="d09-trace"), fixture=self.fixture)
        trace = build_topology_frontier_trace(runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.stage_receipts), 9)
        self.assertEqual(len(trace.events), 9)

    def test_runtime_comparison_is_equivalent(self) -> None:
        left = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="left"), fixture=self.fixture)
        right = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="right"), fixture=self.fixture)
        comparison = compare_topology_frontier_runs(left, right)
        self.assertTrue(comparison.equivalent)
        self.assertEqual(comparison.state_changes, ())


if __name__ == "__main__":
    unittest.main()
