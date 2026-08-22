from __future__ import annotations

import csv
import io
import json
import unittest

from glio_noncode.chromatin_alpha_frontier_accessibility import (
    evaluate_chromatin_alpha_frontier_accessibility,
)
from glio_noncode.chromatin_alpha_frontier_adapters import build_chromatin_alpha_frontier_adapters
from glio_noncode.chromatin_alpha_frontier_checks import run_chromatin_alpha_frontier_invariants
from glio_noncode.chromatin_alpha_frontier_cli import run_chromatin_alpha_frontier_operation
from glio_noncode.chromatin_alpha_frontier_compliance import (
    evaluate_chromatin_alpha_frontier_boundary,
)
from glio_noncode.chromatin_alpha_frontier_contracts import build_chromatin_alpha_frontier_contracts
from glio_noncode.chromatin_alpha_frontier_exports import (
    export_chromatin_alpha_frontier_json,
    export_chromatin_alpha_frontier_manifest,
    export_chromatin_alpha_frontier_review_csv,
    render_chromatin_alpha_frontier_review_markdown,
)
from glio_noncode.chromatin_alpha_frontier_fixture_eval import (
    evaluate_chromatin_alpha_frontier_fixture,
)
from glio_noncode.chromatin_alpha_frontier_lineage import (
    build_chromatin_alpha_frontier_lineage,
    verify_chromatin_alpha_frontier_lineage,
)
from glio_noncode.chromatin_alpha_frontier_metrics import build_chromatin_alpha_frontier_metrics
from glio_noncode.chromatin_alpha_frontier_observability import build_chromatin_alpha_frontier_trace
from glio_noncode.chromatin_alpha_frontier_pipeline import run_chromatin_alpha_frontier_pipeline
from glio_noncode.chromatin_alpha_frontier_policy import evaluate_chromatin_alpha_frontier_policy
from glio_noncode.chromatin_alpha_frontier_public_data import (
    CHROMATIN_ALPHA_FRONTIER_BOUNDARY,
    CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
    ChromatinAlphaFrontierOperation,
    audit_chromatin_alpha_frontier_data,
    build_chromatin_alpha_frontier_catalog,
    default_chromatin_alpha_frontier_fixture,
)
from glio_noncode.chromatin_alpha_frontier_quality_gate import (
    build_chromatin_alpha_frontier_quality,
)
from glio_noncode.chromatin_alpha_frontier_reconciliation import reconcile_chromatin_alpha_frontier
from glio_noncode.chromatin_alpha_frontier_release import build_chromatin_alpha_frontier_release
from glio_noncode.chromatin_alpha_frontier_replay import (
    chromatin_alpha_frontier_replay_is_deterministic,
    compare_chromatin_alpha_frontier_replays,
    replay_chromatin_alpha_frontier,
)
from glio_noncode.chromatin_alpha_frontier_reports import build_chromatin_alpha_frontier_report
from glio_noncode.chromatin_alpha_frontier_review_queue import (
    ChromatinAlphaFrontierReviewPriority,
    build_chromatin_alpha_frontier_review_queue,
)
from glio_noncode.chromatin_alpha_frontier_runbook import default_chromatin_alpha_frontier_runbook
from glio_noncode.chromatin_alpha_frontier_runtime import run_chromatin_alpha_frontier_runtime
from glio_noncode.chromatin_alpha_frontier_scenario_matrix import (
    build_chromatin_alpha_frontier_scenario_matrix,
    evaluate_chromatin_alpha_frontier_scenarios,
)
from glio_noncode.chromatin_alpha_frontier_schema import (
    chromatin_alpha_frontier_schema_manifest,
    validate_chromatin_alpha_frontier_schema,
)
from glio_noncode.chromatin_alpha_frontier_source_registry import (
    build_chromatin_alpha_frontier_source_registry,
)
from glio_noncode.chromatin_alpha_frontier_thresholds import (
    build_chromatin_alpha_frontier_threshold_report,
)
from glio_noncode.chromatin_alpha_frontier_validation_matrix import (
    build_chromatin_alpha_frontier_validation_matrix,
    validate_chromatin_alpha_frontier_matrix,
)
from glio_noncode.chromatin_alpha_frontier_views import build_chromatin_alpha_frontier_view


class ChromatinAlphaFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_chromatin_alpha_frontier_fixture()
        cls.evaluation = evaluate_chromatin_alpha_frontier_fixture(cls.fixture)

    def test_fixture_has_exact_context_balance_and_sources(self) -> None:
        self.assertEqual(self.fixture.context_key, CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, CHROMATIN_ALPHA_FRONTIER_BOUNDARY)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))
        self.assertTrue(all(source.uri.startswith("https://") for source in self.fixture.sources))

    def test_catalog_is_balanced_by_operation(self) -> None:
        catalog = build_chromatin_alpha_frontier_catalog(self.fixture)
        self.assertEqual(
            catalog.operation_ids,
            tuple(operation.value for operation in ChromatinAlphaFrontierOperation),
        )
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.source_ids), 5)
        for operation in ChromatinAlphaFrontierOperation:
            self.assertEqual(len(self.fixture.operation_records(operation)), 4)

    def test_data_audit_passes(self) -> None:
        audit = audit_chromatin_alpha_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertGreaterEqual(len(audit.checks), 15)

    def test_evaluation_matches_all_positive_and_control_paths(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual((self.evaluation.positive_count, self.evaluation.control_count), (4, 12))
        self.assertEqual(
            (self.evaluation.state_match_count, self.evaluation.issue_match_count), (16, 16)
        )
        self.assertEqual(self.evaluation.failed_record_ids, ())
        self.assertTrue(
            all(
                item.adapter.content_address.startswith("sha256:")
                for item in self.evaluation.records
            )
        )

    def test_control_states_keep_uncertainty_visible(self) -> None:
        states = {item.observed_state for item in self.evaluation.records if item.role == "control"}
        self.assertEqual(states, {"ambiguous", "out_of_domain", "partial"})
        self.assertTrue(
            any("context_mismatch" in item.observed_issue_codes for item in self.evaluation.records)
        )
        self.assertTrue(any(item.observed_issue_codes for item in self.evaluation.records))

    def test_adapter_registry_covers_primitives(self) -> None:
        registry = build_chromatin_alpha_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        for operation in ChromatinAlphaFrontierOperation:
            spec = registry.for_operation(operation)
            self.assertEqual(spec.operation, operation)
            self.assertTrue(spec.required_fields)
            self.assertTrue(spec.primitive)

    def test_positive_results_have_measurements_and_warnings(self) -> None:
        for item in self.evaluation.records:
            if item.role == "positive":
                self.assertEqual(item.observed_state, "supported")
                self.assertTrue(item.adapter.measurements)
                self.assertTrue(item.adapter.warnings)

    def test_contracts_schema_and_manifest_pass(self) -> None:
        contracts = build_chromatin_alpha_frontier_contracts()
        schema = validate_chromatin_alpha_frontier_schema(self.fixture, self.evaluation)
        manifest = chromatin_alpha_frontier_schema_manifest()
        self.assertTrue(contracts.accepted)
        self.assertEqual(contracts.unique_operations, 4)
        self.assertTrue(schema.accepted)
        self.assertEqual(schema.failed_check_ids, ())
        self.assertEqual(len(manifest["contracts"]), 4)
        self.assertTrue(manifest["content_address"].startswith("sha256:"))

    def test_metrics_policy_and_reconciliation_pass(self) -> None:
        metrics = build_chromatin_alpha_frontier_metrics(self.evaluation)
        policy = evaluate_chromatin_alpha_frontier_policy(self.evaluation)
        reconciliation = reconcile_chromatin_alpha_frontier(self.evaluation)
        self.assertTrue(metrics.accepted)
        self.assertTrue(policy.accepted)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(metrics.operation_counts[ChromatinAlphaFrontierOperation.PURITY.value], 4)
        self.assertEqual(policy.release_count, 4)
        self.assertEqual(policy.review_count, 12)
        self.assertEqual(reconciliation.difference_count, 0)

    def test_lineage_connects_results_to_sources(self) -> None:
        lineage = build_chromatin_alpha_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertEqual(lineage.source_count, 5)
        self.assertEqual(lineage.record_count, 16)
        self.assertGreaterEqual(len(lineage.edges), 16)
        self.assertTrue(
            verify_chromatin_alpha_frontier_lineage(lineage, self.fixture, self.evaluation)
        )

    def test_quality_gate_retains_controls_and_passes(self) -> None:
        data = audit_chromatin_alpha_frontier_data(self.fixture)
        schema = validate_chromatin_alpha_frontier_schema(self.fixture, self.evaluation)
        metrics = build_chromatin_alpha_frontier_metrics(self.evaluation)
        reconciliation = reconcile_chromatin_alpha_frontier(self.evaluation)
        quality = build_chromatin_alpha_frontier_quality(
            self.fixture, data, schema, self.evaluation, metrics, reconciliation
        )
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.failed_check_ids, ())
        self.assertGreaterEqual(quality.passed_count, 20)

    def test_runtime_has_ten_passed_stages(self) -> None:
        runtime = run_chromatin_alpha_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 10)
        self.assertTrue(all(stage.status == "passed" for stage in runtime.stages))

    def test_release_bundle_artifacts_and_source_registry_pass(self) -> None:
        runtime = run_chromatin_alpha_frontier_runtime(fixture=self.fixture)
        release = build_chromatin_alpha_frontier_release(runtime)
        from glio_noncode.chromatin_alpha_frontier_artifacts import (
            build_chromatin_alpha_frontier_artifacts,
        )
        from glio_noncode.chromatin_alpha_frontier_bundle import (
            build_chromatin_alpha_frontier_bundle,
        )

        bundle = build_chromatin_alpha_frontier_bundle(self.fixture, self.evaluation, release)
        artifacts = build_chromatin_alpha_frontier_artifacts(runtime.quality, release, bundle)
        registry = build_chromatin_alpha_frontier_source_registry(self.fixture)
        self.assertTrue(release.accepted)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertTrue(registry.accepted)
        self.assertEqual(len(artifacts.artifacts), 4)
        self.assertEqual(len(registry.entries), 5)

    def test_view_and_review_queue_route_all_controls(self) -> None:
        runtime = run_chromatin_alpha_frontier_runtime(fixture=self.fixture)
        release = build_chromatin_alpha_frontier_release(runtime)
        view = build_chromatin_alpha_frontier_view(
            self.fixture, self.evaluation, runtime.policy, release
        )
        queue = build_chromatin_alpha_frontier_review_queue(view, release)
        self.assertTrue(view.accepted)
        self.assertEqual(view.review_count, 12)
        self.assertEqual(len(view.accepted_record_ids), 4)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.items), 12)
        self.assertEqual(len(queue.required_items), 9)
        self.assertEqual(queue.items[0].priority, ChromatinAlphaFrontierReviewPriority.CONTEXT)

    def test_observability_has_stage_and_row_events(self) -> None:
        runtime = run_chromatin_alpha_frontier_runtime(fixture=self.fixture)
        trace = build_chromatin_alpha_frontier_trace(runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events_for("stage_completed")), 10)
        self.assertEqual(len(trace.events_for("record_evaluated")), 16)
        self.assertEqual(len(trace.by_severity("error")), 0)

    def test_accessibility_boundary_and_invariants_pass(self) -> None:
        accessibility = evaluate_chromatin_alpha_frontier_accessibility(
            self.fixture, self.evaluation
        )
        boundary = evaluate_chromatin_alpha_frontier_boundary(self.fixture, self.evaluation)
        invariants = run_chromatin_alpha_frontier_invariants(self.fixture, self.evaluation)
        self.assertTrue(accessibility.accepted)
        self.assertTrue(boundary.accepted)
        self.assertTrue(invariants.accepted)
        self.assertEqual(boundary.blocking_failures, ())
        self.assertEqual(invariants.failed_ids, ())

    def test_scenarios_thresholds_and_validation_are_complete(self) -> None:
        scenarios = evaluate_chromatin_alpha_frontier_scenarios(
            build_chromatin_alpha_frontier_scenario_matrix()
        )
        thresholds = build_chromatin_alpha_frontier_threshold_report()
        validation = build_chromatin_alpha_frontier_validation_matrix()
        self.assertTrue(scenarios.accepted)
        self.assertTrue(thresholds.accepted)
        self.assertTrue(validate_chromatin_alpha_frontier_matrix(validation))
        self.assertEqual(len(scenarios.scenarios), 32)
        self.assertEqual(len(thresholds.results), 7)
        self.assertEqual(len(validation.cases), 36)

    def test_runbook_is_ordered_and_complete(self) -> None:
        runbook = default_chromatin_alpha_frontier_runbook()
        self.assertEqual(len(runbook.steps), 18)
        self.assertIn("chromatin-alpha-frontier-evaluate", runbook.commands())
        self.assertEqual(len(runbook.by_phase("package")), 6)

    def test_replay_is_deterministic(self) -> None:
        left = replay_chromatin_alpha_frontier(self.fixture, replay_id="left")
        right = replay_chromatin_alpha_frontier(self.fixture, replay_id="right")
        comparison = compare_chromatin_alpha_frontier_replays(left, right)
        self.assertTrue(comparison.accepted)
        self.assertTrue(chromatin_alpha_frontier_replay_is_deterministic(self.fixture))

    def test_report_and_exports_are_parseable(self) -> None:
        runtime = run_chromatin_alpha_frontier_runtime(fixture=self.fixture)
        release = build_chromatin_alpha_frontier_release(runtime)
        view = build_chromatin_alpha_frontier_view(
            self.fixture, self.evaluation, runtime.policy, release
        )
        report = build_chromatin_alpha_frontier_report(
            self.fixture, self.evaluation, runtime.metrics, view
        )
        csv_text = export_chromatin_alpha_frontier_review_csv(view)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        parsed = json.loads(export_chromatin_alpha_frontier_json(report))
        markdown = render_chromatin_alpha_frontier_review_markdown(view)
        manifest = export_chromatin_alpha_frontier_manifest(report, csv_text=csv_text)
        self.assertTrue(report.accepted)
        self.assertEqual(len(rows), 16)
        self.assertEqual(parsed["report_id"], report.report_id)
        self.assertIn("Chromatin-alpha frontier review", markdown)
        self.assertTrue(manifest["manifest_address"].startswith("sha256:"))

    def test_pipeline_exercises_all_surfaces(self) -> None:
        pipeline = run_chromatin_alpha_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertEqual(len(pipeline.addresses()), 17)
        self.assertTrue(all(value.startswith("sha256:") for value in pipeline.addresses().values()))
        self.assertEqual(pipeline.review_view.summary["release_count"], 4)
        self.assertEqual(pipeline.report.section("review").section_id, "review")

    def test_cli_operations_are_json_compatible(self) -> None:
        operations = (
            "chromatin-alpha-frontier-fixture",
            "chromatin-alpha-frontier-data",
            "chromatin-alpha-frontier-evaluate",
            "chromatin-alpha-frontier-replay",
            "chromatin-alpha-frontier-quality",
            "chromatin-alpha-frontier-contracts",
            "chromatin-alpha-frontier-adapters",
            "chromatin-alpha-frontier-catalog",
            "chromatin-alpha-frontier-schema",
            "chromatin-alpha-frontier-sources",
            "run-chromatin-alpha-frontier-pipeline",
        )
        for operation in operations:
            with self.subTest(operation=operation):
                payload = run_chromatin_alpha_frontier_operation(operation)
                encoded = json.dumps(payload, sort_keys=True)
                self.assertTrue(encoded.startswith("{"))
                self.assertIn("content_address", encoded)


if __name__ == "__main__":
    unittest.main()
