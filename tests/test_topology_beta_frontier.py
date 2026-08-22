from __future__ import annotations

import json
import unittest

from glio_noncode.topology_beta_frontier_accessibility import evaluate_topology_beta_frontier_accessibility
from glio_noncode.topology_beta_frontier_adapters import build_topology_beta_frontier_adapters, execute_topology_beta_frontier_record
from glio_noncode.topology_beta_frontier_artifacts import build_topology_beta_frontier_artifacts
from glio_noncode.topology_beta_frontier_bundle import build_topology_beta_frontier_bundle
from glio_noncode.topology_beta_frontier_candidate_depth import audit_topology_beta_frontier_candidates
from glio_noncode.topology_beta_frontier_catalog import build_topology_beta_frontier_catalog
from glio_noncode.topology_beta_frontier_checks import run_topology_beta_frontier_invariants
from glio_noncode.topology_beta_frontier_cli import TOPOLOGY_BETA_FRONTIER_COMMANDS, run_topology_beta_frontier_operation
from glio_noncode.topology_beta_frontier_compliance import evaluate_topology_beta_frontier_boundary
from glio_noncode.topology_beta_frontier_contracts import build_topology_beta_frontier_contracts
from glio_noncode.topology_beta_frontier_delta_depth import audit_topology_beta_frontier_deltas
from glio_noncode.topology_beta_frontier_depth import audit_topology_beta_frontier_depth
from glio_noncode.topology_beta_frontier_exports import export_topology_beta_frontier_manifest, export_topology_beta_frontier_review_csv, render_topology_beta_frontier_review_markdown
from glio_noncode.topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_integrity import evaluate_topology_beta_frontier_integrity
from glio_noncode.topology_beta_frontier_lineage import build_topology_beta_frontier_lineage
from glio_noncode.topology_beta_frontier_metrics import build_topology_beta_frontier_metrics
from glio_noncode.topology_beta_frontier_observability import build_topology_beta_frontier_trace
from glio_noncode.topology_beta_frontier_pipeline import run_topology_beta_frontier_pipeline
from glio_noncode.topology_beta_frontier_policy import evaluate_topology_beta_frontier_policy
from glio_noncode.topology_beta_frontier_provenance import build_topology_beta_frontier_provenance
from glio_noncode.topology_beta_frontier_public_data import TopologyBetaFrontierOperation, audit_topology_beta_frontier_data, default_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_quality_gate import build_topology_beta_frontier_quality
from glio_noncode.topology_beta_frontier_reconciliation import reconcile_topology_beta_frontier
from glio_noncode.topology_beta_frontier_release import build_topology_beta_frontier_release
from glio_noncode.topology_beta_frontier_replay import replay_topology_beta_frontier
from glio_noncode.topology_beta_frontier_reports import build_topology_beta_frontier_report
from glio_noncode.topology_beta_frontier_review_queue import build_topology_beta_frontier_review_queue
from glio_noncode.topology_beta_frontier_runbook import default_topology_beta_frontier_runbook
from glio_noncode.topology_beta_frontier_runtime import TopologyBetaFrontierRuntimeOptions, run_topology_beta_frontier_runtime
from glio_noncode.topology_beta_frontier_scenario_matrix import build_topology_beta_frontier_scenario_matrix, evaluate_topology_beta_frontier_scenarios
from glio_noncode.topology_beta_frontier_schema import validate_topology_beta_frontier_schema
from glio_noncode.topology_beta_frontier_source_registry import build_topology_beta_frontier_source_registry
from glio_noncode.topology_beta_frontier_thresholds import build_topology_beta_frontier_threshold_report
from glio_noncode.topology_beta_frontier_validation_matrix import build_topology_beta_frontier_validation_matrix, validate_topology_beta_frontier_matrix
from glio_noncode.topology_beta_frontier_views import build_topology_beta_frontier_view


class TopologyBetaFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_beta_frontier_fixture()
        self.evaluation = evaluate_topology_beta_frontier_fixture(self.fixture)

    def test_fixture_is_closed_and_balanced(self) -> None:
        self.assertEqual(len(self.fixture.sources), 4)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.fixture.records))

    def test_every_operation_has_one_positive_and_three_controls(self) -> None:
        for operation in TopologyBetaFrontierOperation:
            rows = self.fixture.operation_records(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role.value == "positive" for item in rows), 1)
            self.assertEqual(sum(item.role.value == "control" for item in rows), 3)

    def test_public_data_audit_and_sources_pass(self) -> None:
        self.assertTrue(audit_topology_beta_frontier_data(self.fixture).accepted)
        sources = build_topology_beta_frontier_source_registry(self.fixture)
        self.assertTrue(sources.accepted)
        self.assertEqual({item.source_kind for item in sources.entries}, {"loop_stripe_aggregate", "promoter_capture_aggregate", "enhancer_contact_aggregate", "enhancer_activity_aggregate"})
        self.assertTrue(all(item.record_count > 0 for item in sources.entries))

    def test_adapter_registry_has_operation_specific_fields(self) -> None:
        registry = build_topology_beta_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        self.assertIn("two_anchor_coordinates", registry.for_operation("loop_stripe").output_fields)
        self.assertIn("bait_id", registry.for_operation("promoter_capture").output_fields)
        self.assertIn("normalized_contact_score", registry.for_operation("enhancer_promoter_contact").output_fields)
        self.assertIn("activity_component", registry.for_operation("activity_by_contact").output_fields)

    def test_replay_matches_all_states_and_issue_floors(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(self.evaluation.state_match_count, 16)
        self.assertEqual(self.evaluation.issue_match_count, 16)
        self.assertEqual(self.evaluation.failed_record_ids, ())

    def test_loop_stripe_states_retain_coordinates_signal_and_metadata(self) -> None:
        rows = self.evaluation.by_operation("loop_stripe")
        self.assertEqual([item.observed_state for item in rows], ["supported", "partial", "ambiguous", "out_of_domain"])
        self.assertEqual(rows[0].adapter.measurements["observation_count"], 1)
        self.assertIn("loop", rows[0].adapter.measurements["feature_kinds"])
        self.assertIn("missing_loop_metadata", rows[1].adapter.issue_codes)
        self.assertIn("replicate_disagreement", rows[2].adapter.issue_codes)
        self.assertIn("context_mismatch", rows[3].adapter.issue_codes)

    def test_promoter_capture_states_retain_identity_bait_and_context(self) -> None:
        rows = self.evaluation.by_operation("promoter_capture")
        self.assertEqual([item.observed_state for item in rows], ["supported", "partial", "ambiguous", "out_of_domain"])
        self.assertEqual(rows[0].adapter.measurements["promoters"], ["GENE1"])
        self.assertEqual(rows[0].adapter.measurements["targets"], ["enh-1"])
        self.assertEqual(rows[0].adapter.measurements["bait_ids"], ["bait-1"])
        self.assertIn("missing_bait_id", rows[1].adapter.issue_codes)

    def test_contact_score_states_preserve_bounded_signal_and_missingness(self) -> None:
        rows = self.evaluation.by_operation("enhancer_promoter_contact")
        self.assertEqual([item.observed_state for item in rows], ["supported", "ambiguous", "out_of_domain", "absent"])
        self.assertEqual(rows[0].adapter.measurements["normalized_contact_score"], 0.6)
        self.assertEqual(rows[1].adapter.measurements["signal_spread"], 8.0)
        self.assertIn("context_mismatch", rows[2].adapter.issue_codes)
        self.assertIn("no_contact_observations", rows[3].adapter.issue_codes)

    def test_activity_by_contact_retains_components_model_and_context_gate(self) -> None:
        rows = self.evaluation.by_operation("activity_by_contact")
        self.assertEqual([item.observed_state for item in rows], ["supported", "abstained", "ambiguous", "out_of_domain"])
        self.assertEqual(rows[0].adapter.measurements["contact_component"], 0.6)
        self.assertEqual(rows[0].adapter.measurements["activity_component"], 0.8)
        self.assertEqual(rows[0].adapter.measurements["activity_by_contact_score"], 0.48)
        self.assertIn("missing_activity", rows[1].adapter.issue_codes)
        self.assertIn("component_disagreement", rows[2].adapter.issue_codes)
        self.assertIn("context_mismatch", rows[3].adapter.issue_codes)

    def test_direct_adapter_addresses_are_stable(self) -> None:
        for record in self.fixture.records:
            result = execute_topology_beta_frontier_record(record)
            self.assertEqual(result.record_id, record.record_id)
            self.assertTrue(result.content_address.startswith("sha256:"))
            self.assertEqual(result.source_ids, record.source_ids)

    def test_contracts_schema_metrics_policy_lineage_and_reconciliation_pass(self) -> None:
        contracts = build_topology_beta_frontier_contracts()
        self.assertTrue(contracts.accepted)
        self.assertEqual(len(contracts.contracts), 4)
        self.assertTrue(all("public_aggregate" in item.required_fields for item in contracts.contracts))
        schema = validate_topology_beta_frontier_schema(self.fixture, self.evaluation)
        self.assertTrue(schema.accepted)
        metrics = build_topology_beta_frontier_metrics(self.evaluation)
        self.assertTrue(metrics.accepted)
        self.assertEqual(metrics.get("record_count").value, 16.0)
        self.assertEqual(metrics.get("state_match_rate").value, 1.0)
        self.assertEqual(evaluate_topology_beta_frontier_policy(self.evaluation).review_count, 12)
        self.assertTrue(build_topology_beta_frontier_lineage(self.fixture, self.evaluation).accepted)
        self.assertTrue(reconcile_topology_beta_frontier(self.evaluation).accepted)

    def test_quality_depth_candidates_deltas_and_validation_pass(self) -> None:
        schema = validate_topology_beta_frontier_schema(self.fixture, self.evaluation)
        reconciliation = reconcile_topology_beta_frontier(self.evaluation)
        quality = build_topology_beta_frontier_quality(self.fixture, audit_topology_beta_frontier_data(self.fixture), schema, self.evaluation, reconciliation)
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.quality_score, 1.0)
        depth = audit_topology_beta_frontier_depth(self.fixture, self.evaluation)
        self.assertTrue(depth.accepted)
        self.assertGreaterEqual(depth.mean_depth, 0.95)
        self.assertTrue(audit_topology_beta_frontier_candidates(self.evaluation).accepted)
        self.assertTrue(audit_topology_beta_frontier_deltas(self.evaluation).accepted)
        validation = build_topology_beta_frontier_validation_matrix(self.evaluation)
        self.assertTrue(validate_topology_beta_frontier_matrix(validation))
        self.assertEqual(len(validation.cells), 8)

    def test_scenarios_include_all_missingness_and_context_paths(self) -> None:
        matrix = build_topology_beta_frontier_scenario_matrix(self.evaluation)
        self.assertTrue(matrix.accepted)
        summary = evaluate_topology_beta_frontier_scenarios(matrix)
        self.assertEqual(summary["scenario_count"], 6)
        self.assertEqual(summary["passed_count"], 6)

    def test_integrity_boundary_accessibility_and_invariants_pass(self) -> None:
        self.assertTrue(evaluate_topology_beta_frontier_integrity(self.fixture, self.evaluation).accepted)
        self.assertTrue(evaluate_topology_beta_frontier_boundary(self.fixture, self.evaluation).accepted)
        self.assertTrue(evaluate_topology_beta_frontier_accessibility(self.evaluation).accepted)
        self.assertTrue(run_topology_beta_frontier_invariants(self.fixture, self.evaluation).accepted)

    def test_provenance_and_lineage_close_every_record(self) -> None:
        lineage = build_topology_beta_frontier_lineage(self.fixture, self.evaluation)
        graph = build_topology_beta_frontier_provenance(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertTrue(graph.accepted)
        self.assertEqual(graph.source_count, 4)
        self.assertEqual(graph.record_count, 16)
        self.assertEqual(graph.result_count, 16)
        self.assertEqual(len(graph.nodes_by_kind("result")), 16)
        self.assertGreaterEqual(len(graph.edges), 32)
        self.assertTrue(all(item.aggregate for item in graph.nodes))

    def test_review_queue_and_view_are_complete(self) -> None:
        queue = build_topology_beta_frontier_review_queue(self.evaluation)
        view = build_topology_beta_frontier_view(self.evaluation)
        self.assertTrue(queue.accepted)
        self.assertEqual(queue.count, 12)
        self.assertEqual(len(queue.for_priority("high")), 8)
        self.assertTrue(view.accepted)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(view.for_state("supported")), 4)

    def test_release_bundle_artifacts_and_report_pass(self) -> None:
        pipeline = run_topology_beta_frontier_pipeline(self.fixture)
        release = build_topology_beta_frontier_release(self.fixture, self.evaluation, pipeline.quality)
        bundle = build_topology_beta_frontier_bundle(self.fixture, release, pipeline.metrics, pipeline.deltas)
        artifacts = build_topology_beta_frontier_artifacts(bundle, self.evaluation)
        report = build_topology_beta_frontier_report(self.evaluation, pipeline.metrics, pipeline.quality)
        self.assertTrue(release.publishable)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertEqual(len(artifacts.artifacts), 20)
        self.assertTrue(report.accepted)

    def test_pipeline_has_twelve_accepted_stages(self) -> None:
        pipeline = run_topology_beta_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertEqual(pipeline.failed_stages, ())
        self.assertEqual(len(pipeline.stages), 12)
        self.assertTrue(all(item.status == "passed" for item in pipeline.stages))
        self.assertTrue(all(item.detail for item in pipeline.stages))

    def test_replay_receipt_and_trace_are_repeatable(self) -> None:
        replay = replay_topology_beta_frontier(self.fixture)
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.expected_address, replay.replay_address)
        trace = build_topology_beta_frontier_trace(self.evaluation, "test-run")
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events), 16)
        self.assertEqual(len(trace.for_operation("loop_stripe")), 4)

    def test_runtime_limit_is_enforced(self) -> None:
        self.assertTrue(run_topology_beta_frontier_runtime(fixture=self.fixture).accepted)
        with self.assertRaises(ValueError):
            run_topology_beta_frontier_runtime(TopologyBetaFrontierRuntimeOptions(max_records=15), fixture=self.fixture)

    def test_exports_are_sanitized_and_structured(self) -> None:
        manifest = export_topology_beta_frontier_manifest(self.fixture, self.evaluation)
        self.assertEqual(json.loads(manifest)["fixture"]["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(export_topology_beta_frontier_review_csv(self.evaluation).count("\n"), 17)
        self.assertIn("Domain 09 topology beta review", render_topology_beta_frontier_review_markdown(self.evaluation))
        self.assertNotIn("subject_id", manifest)

    def test_catalog_thresholds_runbook_and_cli_are_closed(self) -> None:
        catalog = build_topology_beta_frontier_catalog()
        self.assertTrue(catalog.accepted)
        self.assertEqual(len(catalog.entries), 4)
        self.assertEqual(catalog.for_operation("activity_by_contact").capability_id, "GNC-D09-C08")
        thresholds = build_topology_beta_frontier_threshold_report()
        self.assertTrue(thresholds.accepted)
        self.assertEqual(thresholds.get("contact_signal_scale").value, 10.0)
        self.assertEqual(len(default_topology_beta_frontier_runbook().steps), 5)
        self.assertEqual(len(TOPOLOGY_BETA_FRONTIER_COMMANDS), 12)
        for operation in TOPOLOGY_BETA_FRONTIER_COMMANDS:
            value = run_topology_beta_frontier_operation(operation)
            self.assertIsInstance(value, dict)
            self.assertTrue(value)


if __name__ == "__main__":
    unittest.main()
