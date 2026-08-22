from __future__ import annotations

import json
import unittest

from glio_noncode.cell_context_beta_frontier_accessibility import (
    evaluate_cell_context_beta_frontier_accessibility,
)
from glio_noncode.cell_context_beta_frontier_adapters import (
    build_cell_context_beta_frontier_adapters,
    execute_cell_context_beta_frontier_record,
)
from glio_noncode.cell_context_beta_frontier_artifacts import (
    build_cell_context_beta_frontier_artifacts,
)
from glio_noncode.cell_context_beta_frontier_bundle import build_cell_context_beta_frontier_bundle
from glio_noncode.cell_context_beta_frontier_candidate_depth import (
    audit_cell_context_beta_frontier_candidates,
)
from glio_noncode.cell_context_beta_frontier_catalog import build_cell_context_beta_frontier_catalog
from glio_noncode.cell_context_beta_frontier_cli import (
    CELL_CONTEXT_BETA_FRONTIER_COMMANDS,
    run_cell_context_beta_frontier_operation,
)
from glio_noncode.cell_context_beta_frontier_compliance import (
    evaluate_cell_context_beta_frontier_boundary,
)
from glio_noncode.cell_context_beta_frontier_contracts import (
    build_cell_context_beta_frontier_contracts,
)
from glio_noncode.cell_context_beta_frontier_depth import audit_cell_context_beta_frontier_depth
from glio_noncode.cell_context_beta_frontier_exports import (
    export_cell_context_beta_frontier_manifest,
    export_cell_context_beta_frontier_review_csv,
    render_cell_context_beta_frontier_review_markdown,
)
from glio_noncode.cell_context_beta_frontier_fixture_eval import (
    evaluate_cell_context_beta_frontier_fixture,
)
from glio_noncode.cell_context_beta_frontier_gate_depth import (
    audit_cell_context_beta_frontier_gates,
)
from glio_noncode.cell_context_beta_frontier_integrity import (
    evaluate_cell_context_beta_frontier_integrity,
)
from glio_noncode.cell_context_beta_frontier_lineage import build_cell_context_beta_frontier_lineage
from glio_noncode.cell_context_beta_frontier_metrics import build_cell_context_beta_frontier_metrics
from glio_noncode.cell_context_beta_frontier_observability import (
    build_cell_context_beta_frontier_trace,
)
from glio_noncode.cell_context_beta_frontier_pipeline import run_cell_context_beta_frontier_pipeline
from glio_noncode.cell_context_beta_frontier_policy import (
    evaluate_cell_context_beta_frontier_policy,
)
from glio_noncode.cell_context_beta_frontier_public_data import (
    CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY,
    CellContextBetaFrontierOperation,
    audit_cell_context_beta_frontier_data,
    default_cell_context_beta_frontier_fixture,
)
from glio_noncode.cell_context_beta_frontier_quality_gate import (
    build_cell_context_beta_frontier_quality,
)
from glio_noncode.cell_context_beta_frontier_reconciliation import (
    reconcile_cell_context_beta_frontier,
)
from glio_noncode.cell_context_beta_frontier_release import build_cell_context_beta_frontier_release
from glio_noncode.cell_context_beta_frontier_replay import replay_cell_context_beta_frontier
from glio_noncode.cell_context_beta_frontier_reports import build_cell_context_beta_frontier_report
from glio_noncode.cell_context_beta_frontier_review_queue import (
    build_cell_context_beta_frontier_review_queue,
)
from glio_noncode.cell_context_beta_frontier_runbook import (
    default_cell_context_beta_frontier_runbook,
)
from glio_noncode.cell_context_beta_frontier_runtime import (
    CellContextBetaFrontierRuntimeOptions,
    run_cell_context_beta_frontier_runtime,
)
from glio_noncode.cell_context_beta_frontier_scenario_matrix import (
    build_cell_context_beta_frontier_scenario_matrix,
    evaluate_cell_context_beta_frontier_scenarios,
)
from glio_noncode.cell_context_beta_frontier_schema import (
    validate_cell_context_beta_frontier_schema,
)
from glio_noncode.cell_context_beta_frontier_source_registry import (
    build_cell_context_beta_frontier_source_registry,
)
from glio_noncode.cell_context_beta_frontier_thresholds import (
    build_cell_context_beta_frontier_threshold_report,
)
from glio_noncode.cell_context_beta_frontier_validation_matrix import (
    build_cell_context_beta_frontier_validation_matrix,
    validate_cell_context_beta_frontier_matrix,
)
from glio_noncode.cell_context_beta_frontier_views import build_cell_context_beta_frontier_view


class CellContextBetaFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_cell_context_beta_frontier_fixture()

    def test_fixture_is_closed_public_aggregate_and_balanced(self) -> None:
        self.assertEqual(self.fixture.context_key, CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.sources), 4)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(all(item.content_address for item in self.fixture.records))
        self.assertTrue(all(item.payload["target_context_key"] for item in self.fixture.records))

    def test_data_audit_and_boundary_are_accepted(self) -> None:
        data = audit_cell_context_beta_frontier_data(self.fixture)
        boundary = evaluate_cell_context_beta_frontier_boundary(self.fixture)
        self.assertTrue(data.accepted)
        self.assertTrue(boundary.accepted)
        self.assertEqual(data.failed_check_ids, ())

    def test_each_operation_has_four_records(self) -> None:
        for operation in CellContextBetaFrontierOperation:
            rows = self.fixture.operation_records(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len({item.role for item in rows}), 2)

    def test_adapter_registry_is_complete(self) -> None:
        registry = build_cell_context_beta_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        self.assertEqual(
            registry.for_operation(
                CellContextBetaFrontierOperation.DEVELOPMENTAL_LINEAGE
            ).primitive,
            "DevelopmentalLineagePrior",
        )

    def test_all_rows_execute_to_expected_state(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(evaluation.state_match_count, 16)
        self.assertEqual(evaluation.issue_match_count, 16)
        self.assertEqual(len(evaluation.positive_rows), 4)
        self.assertEqual(len(evaluation.control_rows), 12)

    def test_positive_rows_have_bounded_candidate_measurements(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        for row in evaluation.positive_rows:
            self.assertTrue(row.adapter.measurements["candidate_ids"])
            self.assertGreaterEqual(row.adapter.measurements["uncertainty"], 0)
            self.assertLessEqual(row.adapter.measurements["uncertainty"], 1)
            self.assertTrue(row.adapter.measurements["source_versions"])

    def test_partial_controls_preserve_parser_issue_code(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        partial = evaluation.by_state("partial")
        self.assertEqual(len(partial), 4)
        self.assertTrue(
            all("invalid_context_prior_row" in item.observed_issue_codes for item in partial)
        )

    def test_ambiguity_controls_retain_alternatives(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        ambiguous = evaluation.by_state("ambiguous")
        self.assertEqual(len(ambiguous), 4)
        self.assertTrue(
            all(len(item.adapter.measurements["candidate_ids"]) == 2 for item in ambiguous)
        )
        self.assertTrue(
            all(item.adapter.measurements["selected_candidate_id"] is None for item in ambiguous)
        )

    def test_domain_controls_are_explicit_refusals(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        refused = evaluation.by_state("out_of_domain")
        self.assertEqual(len(refused), 4)
        self.assertTrue(all("context" in item.adapter.detail.lower() for item in refused))

    def test_schema_contracts_and_sources(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        self.assertTrue(build_cell_context_beta_frontier_contracts().accepted)
        self.assertTrue(
            validate_cell_context_beta_frontier_schema(self.fixture, evaluation).accepted
        )
        sources = build_cell_context_beta_frontier_source_registry(self.fixture)
        self.assertTrue(sources.accepted)
        self.assertEqual(len(sources.entries), 4)

    def test_metrics_are_nonnegative_and_complete(self) -> None:
        metrics = build_cell_context_beta_frontier_metrics(
            evaluate_cell_context_beta_frontier_fixture(self.fixture)
        )
        self.assertTrue(metrics.accepted)
        self.assertEqual(metrics.get("record_count").value, 16)
        self.assertEqual(metrics.get("domain_refusal_count").value, 4)
        self.assertGreaterEqual(metrics.get("mean_uncertainty").value, 0)

    def test_policy_queues_non_support_states(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        policy = evaluate_cell_context_beta_frontier_policy(evaluation)
        self.assertTrue(policy.accepted)
        self.assertEqual(policy.review_count, 12)
        self.assertEqual(len(policy.decisions), 16)
        self.assertEqual(policy.decisions[0].action, "retain_research_prior")

    def test_lineage_and_reconciliation_retain_all_rows(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        lineage = build_cell_context_beta_frontier_lineage(self.fixture, evaluation)
        reconciliation = reconcile_cell_context_beta_frontier(evaluation)
        self.assertTrue(lineage.accepted)
        self.assertGreaterEqual(len(lineage.edges), 16)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.mismatches, ())

    def test_quality_gate_and_integrity_are_accepted(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        schema = validate_cell_context_beta_frontier_schema(self.fixture, evaluation)
        quality = build_cell_context_beta_frontier_quality(
            self.fixture,
            audit_cell_context_beta_frontier_data(self.fixture),
            schema,
            evaluation,
            reconcile_cell_context_beta_frontier(evaluation),
        )
        integrity = evaluate_cell_context_beta_frontier_integrity(self.fixture, evaluation)
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.passed_count, 8)
        self.assertTrue(integrity.accepted)

    def test_depth_gate_and_candidate_audits_are_deep(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        depth = audit_cell_context_beta_frontier_depth(self.fixture, evaluation)
        gates = audit_cell_context_beta_frontier_gates(evaluation)
        candidates = audit_cell_context_beta_frontier_candidates(evaluation)
        self.assertTrue(depth.accepted)
        self.assertGreaterEqual(depth.mean_depth, 0.8)
        self.assertTrue(gates.accepted)
        self.assertEqual(len(gates.gates), 4)
        self.assertTrue(candidates.accepted)
        self.assertGreaterEqual(candidates.candidate_count, 16)

    def test_validation_and_scenario_surfaces(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        matrix = build_cell_context_beta_frontier_validation_matrix(evaluation)
        scenarios = build_cell_context_beta_frontier_scenario_matrix(evaluation)
        self.assertTrue(matrix.accepted)
        self.assertTrue(validate_cell_context_beta_frontier_matrix(matrix))
        self.assertTrue(scenarios.accepted)
        self.assertEqual(len(scenarios.scenarios), 4)
        self.assertEqual(
            evaluate_cell_context_beta_frontier_scenarios(scenarios)["scenario_count"], 4
        )

    def test_replay_is_content_addressed(self) -> None:
        replay = replay_cell_context_beta_frontier(self.fixture)
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.fixture_address, self.fixture.content_address)
        self.assertEqual(replay.state_match_count, 16)

    def test_release_bundle_artifacts_and_report(self) -> None:
        pipeline = run_cell_context_beta_frontier_pipeline(self.fixture)
        release = build_cell_context_beta_frontier_release(
            self.fixture, pipeline.evaluation, pipeline.quality
        )
        bundle = build_cell_context_beta_frontier_bundle(
            self.fixture, release, pipeline.metrics, pipeline.lineage
        )
        artifacts = build_cell_context_beta_frontier_artifacts(bundle, pipeline.evaluation)
        report = build_cell_context_beta_frontier_report(
            pipeline.evaluation, pipeline.metrics, pipeline.quality
        )
        self.assertTrue(release.publishable)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertTrue(report.accepted)
        self.assertEqual(len(artifacts.artifacts), 3)

    def test_view_queue_accessibility_trace_and_runbook(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        view = build_cell_context_beta_frontier_view(evaluation)
        queue = build_cell_context_beta_frontier_review_queue(evaluation)
        accessibility = evaluate_cell_context_beta_frontier_accessibility(evaluation)
        trace = build_cell_context_beta_frontier_trace(evaluation, "run-test")
        runbook = default_cell_context_beta_frontier_runbook()
        self.assertTrue(view.accepted)
        self.assertEqual(view.review_count, 12)
        self.assertEqual(queue.count, 12)
        self.assertTrue(accessibility.accepted)
        self.assertEqual(len(trace.events), 16)
        self.assertEqual(len(runbook.steps), 5)

    def test_thresholds_and_catalog_are_closed(self) -> None:
        thresholds = build_cell_context_beta_frontier_threshold_report()
        catalog = build_cell_context_beta_frontier_catalog()
        self.assertTrue(thresholds.accepted)
        self.assertEqual(thresholds.get("records").value, 16)
        self.assertTrue(catalog.accepted)
        self.assertEqual(len(catalog.entries), 4)

    def test_pipeline_exposes_all_stages_and_accepts(self) -> None:
        pipeline = run_cell_context_beta_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertEqual(pipeline.failed_stages, ())
        self.assertEqual(len(pipeline.stages), 12)
        self.assertTrue(pipeline.depth.accepted)
        self.assertTrue(pipeline.gates.accepted)
        self.assertTrue(pipeline.release.publishable)

    def test_runtime_limits_are_enforced(self) -> None:
        runtime = run_cell_context_beta_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.accepted)
        with self.assertRaises(ValueError):
            run_cell_context_beta_frontier_runtime(
                CellContextBetaFrontierRuntimeOptions(max_records=15), fixture=self.fixture
            )

    def test_exports_are_sanitized_and_parseable(self) -> None:
        evaluation = evaluate_cell_context_beta_frontier_fixture(self.fixture)
        manifest = export_cell_context_beta_frontier_manifest(self.fixture, evaluation)
        parsed = json.loads(manifest)
        csv_text = export_cell_context_beta_frontier_review_csv(evaluation)
        markdown = render_cell_context_beta_frontier_review_markdown(evaluation)
        self.assertEqual(parsed["fixture"]["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(csv_text.count("\n"), 17)
        self.assertIn("Domain 08 beta context prior review", markdown)
        self.assertNotIn('"observation_text"', manifest.split('"evaluation"', 1)[0])

    def test_each_cli_operation_returns_jsonable_mapping(self) -> None:
        self.assertEqual(len(CELL_CONTEXT_BETA_FRONTIER_COMMANDS), 12)
        for operation in CELL_CONTEXT_BETA_FRONTIER_COMMANDS:
            result = run_cell_context_beta_frontier_operation(operation)
            self.assertIsInstance(result, dict)
            self.assertTrue(result)

    def test_direct_adapter_result_has_primitive_state(self) -> None:
        result = execute_cell_context_beta_frontier_record(self.fixture.positive_records[0])
        self.assertEqual(result.state, "supported")
        self.assertEqual(result.primitive_state, "supported")
        self.assertEqual(
            result.measurements["target_context_key"], CELL_CONTEXT_BETA_FRONTIER_CONTEXT_KEY
        )


if __name__ == "__main__":
    unittest.main()
