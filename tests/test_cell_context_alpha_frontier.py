from __future__ import annotations

import json
import unittest

from glio_noncode.cell_context_alpha_frontier_accessibility import (
    evaluate_cell_context_alpha_frontier_accessibility,
)
from glio_noncode.cell_context_alpha_frontier_adapters import (
    build_cell_context_alpha_frontier_adapters,
    execute_cell_context_alpha_frontier_record,
)
from glio_noncode.cell_context_alpha_frontier_artifacts import (
    build_cell_context_alpha_frontier_artifacts,
)
from glio_noncode.cell_context_alpha_frontier_bundle import build_cell_context_alpha_frontier_bundle
from glio_noncode.cell_context_alpha_frontier_candidate_depth import (
    audit_cell_context_alpha_frontier_candidates,
)
from glio_noncode.cell_context_alpha_frontier_catalog import (
    build_cell_context_alpha_frontier_catalog,
)
from glio_noncode.cell_context_alpha_frontier_cli import (
    CELL_CONTEXT_ALPHA_FRONTIER_COMMANDS,
    run_cell_context_alpha_frontier_operation,
)
from glio_noncode.cell_context_alpha_frontier_compliance import (
    evaluate_cell_context_alpha_frontier_boundary,
)
from glio_noncode.cell_context_alpha_frontier_contracts import (
    build_cell_context_alpha_frontier_contracts,
)
from glio_noncode.cell_context_alpha_frontier_delta_depth import (
    audit_cell_context_alpha_frontier_deltas,
)
from glio_noncode.cell_context_alpha_frontier_depth import audit_cell_context_alpha_frontier_depth
from glio_noncode.cell_context_alpha_frontier_exports import (
    export_cell_context_alpha_frontier_manifest,
    export_cell_context_alpha_frontier_review_csv,
    render_cell_context_alpha_frontier_review_markdown,
)
from glio_noncode.cell_context_alpha_frontier_fixture_eval import (
    evaluate_cell_context_alpha_frontier_fixture,
)
from glio_noncode.cell_context_alpha_frontier_integrity import (
    evaluate_cell_context_alpha_frontier_integrity,
)
from glio_noncode.cell_context_alpha_frontier_lineage import (
    build_cell_context_alpha_frontier_lineage,
)
from glio_noncode.cell_context_alpha_frontier_metrics import (
    build_cell_context_alpha_frontier_metrics,
)
from glio_noncode.cell_context_alpha_frontier_observability import (
    build_cell_context_alpha_frontier_trace,
)
from glio_noncode.cell_context_alpha_frontier_pipeline import (
    run_cell_context_alpha_frontier_pipeline,
)
from glio_noncode.cell_context_alpha_frontier_policy import (
    evaluate_cell_context_alpha_frontier_policy,
)
from glio_noncode.cell_context_alpha_frontier_public_data import (
    CellContextAlphaFrontierOperation,
    audit_cell_context_alpha_frontier_data,
    default_cell_context_alpha_frontier_fixture,
)
from glio_noncode.cell_context_alpha_frontier_quality_gate import (
    build_cell_context_alpha_frontier_quality,
)
from glio_noncode.cell_context_alpha_frontier_reconciliation import (
    reconcile_cell_context_alpha_frontier,
)
from glio_noncode.cell_context_alpha_frontier_release import (
    build_cell_context_alpha_frontier_release,
)
from glio_noncode.cell_context_alpha_frontier_replay import replay_cell_context_alpha_frontier
from glio_noncode.cell_context_alpha_frontier_reports import (
    build_cell_context_alpha_frontier_report,
)
from glio_noncode.cell_context_alpha_frontier_review_queue import (
    build_cell_context_alpha_frontier_review_queue,
)
from glio_noncode.cell_context_alpha_frontier_runbook import (
    default_cell_context_alpha_frontier_runbook,
)
from glio_noncode.cell_context_alpha_frontier_runtime import (
    CellContextAlphaFrontierRuntimeOptions,
    run_cell_context_alpha_frontier_runtime,
)
from glio_noncode.cell_context_alpha_frontier_scenario_matrix import (
    build_cell_context_alpha_frontier_scenario_matrix,
    evaluate_cell_context_alpha_frontier_scenarios,
)
from glio_noncode.cell_context_alpha_frontier_schema import (
    validate_cell_context_alpha_frontier_schema,
)
from glio_noncode.cell_context_alpha_frontier_source_registry import (
    build_cell_context_alpha_frontier_source_registry,
)
from glio_noncode.cell_context_alpha_frontier_thresholds import (
    build_cell_context_alpha_frontier_threshold_report,
)
from glio_noncode.cell_context_alpha_frontier_validation_matrix import (
    build_cell_context_alpha_frontier_validation_matrix,
    validate_cell_context_alpha_frontier_matrix,
)
from glio_noncode.cell_context_alpha_frontier_views import build_cell_context_alpha_frontier_view


class CellContextAlphaFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_cell_context_alpha_frontier_fixture()

    def test_fixture_has_closed_aggregate_counts(self) -> None:
        self.assertEqual(len(self.fixture.sources), 4)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(all(item.content_address for item in self.fixture.records))

    def test_data_and_boundary_audits_pass(self) -> None:
        self.assertTrue(audit_cell_context_alpha_frontier_data(self.fixture).accepted)
        self.assertTrue(evaluate_cell_context_alpha_frontier_boundary(self.fixture).accepted)

    def test_each_operation_has_four_paths(self) -> None:
        for operation in CellContextAlphaFrontierOperation:
            rows = self.fixture.operation_records(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len({item.role for item in rows}), 2)

    def test_adapter_registry_covers_all_operations(self) -> None:
        registry = build_cell_context_alpha_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        self.assertEqual(
            registry.for_operation(CellContextAlphaFrontierOperation.SPATIAL_NICHE).primitive,
            "SpatialNichePrior",
        )

    def test_fixture_evaluation_replays_all_states_and_issues(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(evaluation.state_match_count, 16)
        self.assertEqual(evaluation.issue_match_count, 16)

    def test_spatial_niche_positive_and_ambiguity_are_retained(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        supported = evaluation.by_state("supported")
        ambiguous = evaluation.by_state("ambiguous")
        self.assertTrue(any(item.operation == "spatial_niche_prior" for item in supported))
        self.assertTrue(any(item.operation == "spatial_niche_prior" for item in ambiguous))
        spatial = evaluation.by_operation("spatial_niche_prior")
        self.assertTrue(
            any("perivascular" in item.adapter.measurements["candidate_ids"] for item in spatial)
        )

    def test_core_margin_preserves_delta_and_mixed_label(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        core = evaluation.by_operation("core_margin_territory_prior")
        self.assertEqual(core[0].observed_state, "supported")
        self.assertAlmostEqual(
            core[0].adapter.measurements["results"][0]["core_margin_delta"], 0.64
        )
        self.assertEqual(core[2].adapter.measurements["results"][0]["territory_label"], "mixed")

    def test_recurrence_preserves_phase_rank_and_ambiguity(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        recurrence = evaluation.by_operation("recurrence_state_prior")
        self.assertEqual(recurrence[0].observed_state, "supported")
        self.assertEqual(recurrence[2].observed_state, "ambiguous")
        self.assertIn("primary", recurrence[0].adapter.measurements["candidate_ids"])

    def test_treatment_preserves_induced_stable_and_partial_paths(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        treatment = evaluation.by_operation("treatment_induced_state_prior")
        labels = {
            str(value.get("induction_label"))
            for row in treatment
            for value in row.adapter.measurements.get("results", ())
        }
        self.assertIn("induced", labels)
        self.assertIn("stable", labels)
        self.assertEqual(treatment[1].observed_state, "partial")

    def test_four_foreign_context_controls_refuse_transport(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        refused = evaluation.by_state("out_of_domain")
        self.assertEqual(len(refused), 4)
        self.assertTrue(
            all(
                "context" in row.adapter.issue_codes or row.adapter.state == "out_of_domain"
                for row in refused
            )
        )

    def test_schema_contracts_and_sources_pass(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        self.assertTrue(build_cell_context_alpha_frontier_contracts().accepted)
        self.assertTrue(
            validate_cell_context_alpha_frontier_schema(self.fixture, evaluation).accepted
        )
        self.assertTrue(build_cell_context_alpha_frontier_source_registry(self.fixture).accepted)

    def test_metrics_policy_lineage_and_reconciliation_pass(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        metrics = build_cell_context_alpha_frontier_metrics(evaluation)
        policy = evaluate_cell_context_alpha_frontier_policy(evaluation)
        lineage = build_cell_context_alpha_frontier_lineage(self.fixture, evaluation)
        reconciliation = reconcile_cell_context_alpha_frontier(evaluation)
        self.assertTrue(metrics.accepted)
        self.assertEqual(metrics.get("record_count").value, 16)
        self.assertEqual(policy.review_count, 11)
        self.assertTrue(lineage.accepted)
        self.assertEqual(len(lineage.edges), 16)
        self.assertTrue(reconciliation.accepted)

    def test_quality_integrity_depth_and_delta_surfaces_pass(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        schema = validate_cell_context_alpha_frontier_schema(self.fixture, evaluation)
        quality = build_cell_context_alpha_frontier_quality(
            self.fixture,
            audit_cell_context_alpha_frontier_data(self.fixture),
            schema,
            evaluation,
            reconcile_cell_context_alpha_frontier(evaluation),
        )
        integrity = evaluate_cell_context_alpha_frontier_integrity(self.fixture, evaluation)
        depth = audit_cell_context_alpha_frontier_depth(self.fixture, evaluation)
        candidates = audit_cell_context_alpha_frontier_candidates(evaluation)
        deltas = audit_cell_context_alpha_frontier_deltas(evaluation)
        self.assertTrue(quality.accepted)
        self.assertTrue(integrity.accepted)
        self.assertTrue(depth.accepted)
        self.assertGreaterEqual(depth.mean_depth, 0.8)
        self.assertTrue(candidates.accepted)
        self.assertGreaterEqual(candidates.candidate_count, 8)
        self.assertTrue(deltas.accepted)
        self.assertIn("induced", deltas.labels)

    def test_scenarios_validation_thresholds_and_accessibility_pass(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        matrix = build_cell_context_alpha_frontier_validation_matrix(evaluation)
        scenarios = build_cell_context_alpha_frontier_scenario_matrix(evaluation)
        accessibility = evaluate_cell_context_alpha_frontier_accessibility(evaluation)
        self.assertTrue(validate_cell_context_alpha_frontier_matrix(matrix))
        self.assertTrue(scenarios.accepted)
        self.assertEqual(
            evaluate_cell_context_alpha_frontier_scenarios(scenarios)["scenario_count"], 4
        )
        self.assertTrue(build_cell_context_alpha_frontier_threshold_report().accepted)
        self.assertTrue(accessibility.accepted)

    def test_replay_release_bundle_artifacts_and_report_pass(self) -> None:
        pipeline = run_cell_context_alpha_frontier_pipeline(self.fixture)
        replay = replay_cell_context_alpha_frontier(self.fixture)
        release = build_cell_context_alpha_frontier_release(
            self.fixture, pipeline.evaluation, pipeline.quality
        )
        bundle = build_cell_context_alpha_frontier_bundle(
            self.fixture, release, pipeline.metrics, pipeline.deltas
        )
        artifacts = build_cell_context_alpha_frontier_artifacts(bundle, pipeline.evaluation)
        report = build_cell_context_alpha_frontier_report(
            pipeline.evaluation, pipeline.metrics, pipeline.quality
        )
        self.assertTrue(replay.accepted)
        self.assertTrue(release.publishable)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertTrue(report.accepted)

    def test_view_queue_trace_runbook_and_runtime_pass(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        view = build_cell_context_alpha_frontier_view(evaluation)
        queue = build_cell_context_alpha_frontier_review_queue(evaluation)
        trace = build_cell_context_alpha_frontier_trace(evaluation, "alpha-test")
        runbook = default_cell_context_alpha_frontier_runbook()
        runtime = run_cell_context_alpha_frontier_runtime(fixture=self.fixture)
        self.assertTrue(view.accepted)
        self.assertEqual(view.review_count, 11)
        self.assertEqual(queue.count, 11)
        self.assertEqual(len(trace.events), 16)
        self.assertEqual(len(runbook.steps), 5)
        self.assertTrue(runtime.accepted)
        with self.assertRaises(ValueError):
            run_cell_context_alpha_frontier_runtime(
                CellContextAlphaFrontierRuntimeOptions(max_records=15), fixture=self.fixture
            )

    def test_pipeline_has_twelve_accepted_stages(self) -> None:
        pipeline = run_cell_context_alpha_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertEqual(pipeline.failed_stages, ())
        self.assertEqual(len(pipeline.stages), 12)
        self.assertTrue(pipeline.invariants.accepted)

    def test_pipeline_surfaces_have_distinct_content_addresses(self) -> None:
        pipeline = run_cell_context_alpha_frontier_pipeline(self.fixture)
        addresses = {
            pipeline.fixture.content_address,
            pipeline.evaluation.content_address,
            pipeline.release.content_address,
            pipeline.bundle.content_address,
            pipeline.artifacts.content_address,
        }
        self.assertEqual(len(addresses), 5)
        self.assertTrue(all(address.startswith("sha256:") for address in addresses))
        self.assertTrue(all(len(address) == 71 for address in addresses))

    def test_exports_are_sanitized(self) -> None:
        evaluation = evaluate_cell_context_alpha_frontier_fixture(self.fixture)
        manifest = export_cell_context_alpha_frontier_manifest(self.fixture, evaluation)
        parsed = json.loads(manifest)
        csv_text = export_cell_context_alpha_frontier_review_csv(evaluation)
        markdown = render_cell_context_alpha_frontier_review_markdown(evaluation)
        self.assertEqual(parsed["fixture"]["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(csv_text.count("\n"), 17)
        self.assertIn("Domain 08 context-alpha review", markdown)
        self.assertNotIn('"observation_text"', manifest.split('"evaluation"', 1)[0])

    def test_all_cli_operations_return_mappings(self) -> None:
        self.assertEqual(len(CELL_CONTEXT_ALPHA_FRONTIER_COMMANDS), 12)
        for operation in CELL_CONTEXT_ALPHA_FRONTIER_COMMANDS:
            value = run_cell_context_alpha_frontier_operation(operation)
            self.assertIsInstance(value, dict)
            self.assertTrue(value)

    def test_direct_adapter_has_primitive_state_and_receipts(self) -> None:
        result = execute_cell_context_alpha_frontier_record(self.fixture.positive_records[0])
        self.assertEqual(result.state, "supported")
        self.assertEqual(result.primitive_state, "supported")
        self.assertEqual(result.measurements["source_versions"], ["aggregate-alpha-2026-01"])

    def test_catalog_is_closed(self) -> None:
        catalog = build_cell_context_alpha_frontier_catalog()
        self.assertTrue(catalog.accepted)
        self.assertEqual(len(catalog.entries), 4)
        self.assertEqual(
            catalog.for_operation("treatment_induced_state_prior").capability_id, "GNC-D08-C12"
        )


if __name__ == "__main__":
    unittest.main()
