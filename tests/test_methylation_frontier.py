from __future__ import annotations

import csv
import io
import json
import unittest

from glio_noncode.methylation_frontier_accessibility import (
    evaluate_methylation_frontier_accessibility,
)
from glio_noncode.methylation_frontier_adapters import (
    build_methylation_frontier_adapters,
)
from glio_noncode.methylation_frontier_checks import run_methylation_frontier_invariants
from glio_noncode.methylation_frontier_cli import run_methylation_frontier_operation
from glio_noncode.methylation_frontier_compliance import evaluate_methylation_frontier_boundary
from glio_noncode.methylation_frontier_contracts import build_methylation_frontier_contracts
from glio_noncode.methylation_frontier_exports import (
    export_methylation_frontier_json,
    export_methylation_frontier_manifest,
    export_methylation_frontier_review_rows,
)
from glio_noncode.methylation_frontier_fixture_eval import evaluate_methylation_frontier_fixture
from glio_noncode.methylation_frontier_lineage import build_methylation_frontier_lineage
from glio_noncode.methylation_frontier_metrics import build_methylation_frontier_metrics
from glio_noncode.methylation_frontier_observability import observe_methylation_frontier
from glio_noncode.methylation_frontier_pipeline import run_methylation_frontier_pipeline
from glio_noncode.methylation_frontier_policy import evaluate_methylation_frontier_policy
from glio_noncode.methylation_frontier_public_data import (
    METHYLATION_FRONTIER_BOUNDARY,
    METHYLATION_FRONTIER_CONTEXT_KEY,
    MethylationFrontierOperation,
    MethylationFrontierState,
    audit_methylation_frontier_data,
    build_methylation_frontier_catalog,
    default_methylation_frontier_fixture,
)
from glio_noncode.methylation_frontier_quality_gate import build_methylation_frontier_quality
from glio_noncode.methylation_frontier_reconciliation import reconcile_methylation_frontier
from glio_noncode.methylation_frontier_release import build_methylation_frontier_release
from glio_noncode.methylation_frontier_replay import (
    compare_methylation_frontier_replays,
    methylation_frontier_replay_is_deterministic,
    replay_methylation_frontier,
)
from glio_noncode.methylation_frontier_reports import build_methylation_frontier_report
from glio_noncode.methylation_frontier_review_queue import (
    MethylationFrontierReviewPriority,
    build_methylation_frontier_review_queue,
)
from glio_noncode.methylation_frontier_runbook import default_methylation_frontier_runbook
from glio_noncode.methylation_frontier_runtime import run_methylation_frontier_runtime
from glio_noncode.methylation_frontier_scenario_matrix import (
    build_methylation_frontier_scenario_matrix,
)
from glio_noncode.methylation_frontier_schema import validate_methylation_frontier_schema
from glio_noncode.methylation_frontier_source_registry import (
    build_methylation_frontier_source_registry,
)
from glio_noncode.methylation_frontier_thresholds import build_methylation_frontier_threshold_report
from glio_noncode.methylation_frontier_validation_matrix import (
    build_methylation_frontier_validation_matrix,
    validate_methylation_frontier_matrix,
)
from glio_noncode.methylation_frontier_views import build_methylation_frontier_review_view


class MethylationFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_methylation_frontier_fixture()
        cls.evaluation = evaluate_methylation_frontier_fixture(cls.fixture)

    def test_fixture_identity_and_public_boundary(self) -> None:
        self.assertEqual(self.fixture.context_key, METHYLATION_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, METHYLATION_FRONTIER_BOUNDARY)
        self.assertEqual(len(self.fixture.sources), 4)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))
        self.assertTrue(all(source.uri.startswith("https://") for source in self.fixture.sources))
        self.assertTrue(all(source.checksum for source in self.fixture.sources))

    def test_catalog_is_closed_and_operation_balanced(self) -> None:
        catalog = build_methylation_frontier_catalog(self.fixture)
        self.assertEqual(
            catalog.operations, tuple(operation.value for operation in MethylationFrontierOperation)
        )
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.source_ids), 4)
        self.assertTrue(catalog.content_address.startswith("sha256:"))
        for operation in MethylationFrontierOperation:
            self.assertEqual(len(self.fixture.operation_records(operation)), 4)

    def test_data_audit_passes(self) -> None:
        report = audit_methylation_frontier_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_check_ids, ())
        self.assertGreaterEqual(len(report.checks), 10)

    def test_evaluation_matches_all_expected_paths(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(self.evaluation.positive_count, 4)
        self.assertEqual(self.evaluation.control_count, 12)
        self.assertEqual(self.evaluation.state_match_count, 16)
        self.assertEqual(self.evaluation.issue_match_count, 16)
        self.assertEqual(self.evaluation.failed_record_ids, ())
        self.assertTrue(
            all(
                item.adapter.content_address.startswith("sha256:")
                for item in self.evaluation.records
            )
        )

    def test_expected_control_states_are_present(self) -> None:
        states = {item.observed_state for item in self.evaluation.records if item.role == "control"}
        self.assertIn(MethylationFrontierState.PARTIAL, states)
        self.assertIn(MethylationFrontierState.INVALID, states)
        self.assertIn(MethylationFrontierState.OUT_OF_DOMAIN, states)
        self.assertIn(MethylationFrontierState.ABSTAINED, states)

    def test_each_adapter_has_a_typed_spec(self) -> None:
        registry = build_methylation_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        for operation in MethylationFrontierOperation:
            spec = registry.for_operation(operation)
            self.assertEqual(spec.operation, operation)
            self.assertTrue(spec.primitive)
            self.assertTrue(spec.required_fields)
            self.assertTrue(spec.content_address.startswith("sha256:"))

    def test_positive_adapter_results_expose_operation_evidence(self) -> None:
        for item in self.evaluation.records:
            if item.role != "positive":
                continue
            result = item.adapter
            self.assertEqual(result.state, MethylationFrontierState.SUPPORTED)
            self.assertTrue(result.measurements)
            self.assertTrue(result.warnings)
            self.assertTrue(result.content_address.startswith("sha256:"))

    def test_contracts_cover_every_operation(self) -> None:
        report = build_methylation_frontier_contracts()
        self.assertTrue(report.accepted)
        self.assertEqual(report.unique_operations, 4)
        self.assertEqual(
            {contract.operation for contract in report.contracts}, set(MethylationFrontierOperation)
        )
        self.assertTrue(
            all(contract.boundary == METHYLATION_FRONTIER_BOUNDARY for contract in report.contracts)
        )

    def test_schema_and_boundary_reports_pass(self) -> None:
        schema = validate_methylation_frontier_schema(self.fixture)
        boundary = evaluate_methylation_frontier_boundary(self.fixture, self.evaluation)
        self.assertTrue(schema.accepted)
        self.assertTrue(boundary.accepted)
        self.assertEqual(schema.failed_check_ids, ())
        self.assertEqual(boundary.blocking_failures, ())
        self.assertGreaterEqual(len(schema.checks), 9)
        self.assertGreaterEqual(len(boundary.checks), 10)

    def test_metrics_policy_and_reconciliation_pass(self) -> None:
        metrics = build_methylation_frontier_metrics(self.evaluation)
        policy = evaluate_methylation_frontier_policy(self.evaluation)
        reconciliation = reconcile_methylation_frontier(self.evaluation)
        self.assertTrue(metrics.accepted)
        self.assertTrue(policy.accepted)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(metrics.operation_counts[MethylationFrontierOperation.CPG_CHANGE.value], 4)
        self.assertEqual(policy.release_count, 4)
        self.assertEqual(policy.review_count, 12)
        self.assertEqual(reconciliation.difference_count, 0)

    def test_lineage_connects_every_row_to_source(self) -> None:
        lineage = build_methylation_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertEqual(lineage.record_count, 16)
        self.assertEqual(lineage.source_count, 4)
        self.assertGreaterEqual(len(lineage.edges), 16)
        self.assertTrue(all(edge.result_address.startswith("sha256:") for edge in lineage.edges))
        self.assertGreaterEqual(len(lineage.for_source("encode-methylation")), 12)

    def test_quality_gate_passes_and_retains_controls(self) -> None:
        data = audit_methylation_frontier_data(self.fixture)
        schema = validate_methylation_frontier_schema(self.fixture)
        metrics = build_methylation_frontier_metrics(self.evaluation)
        reconciliation = reconcile_methylation_frontier(self.evaluation)
        quality = build_methylation_frontier_quality(
            self.fixture, data, schema, self.evaluation, metrics, reconciliation
        )
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.failed_check_ids, ())
        self.assertGreaterEqual(quality.passed_count, 20)
        self.assertTrue(any(check.check_id == "out_of_domain_control" for check in quality.checks))

    def test_runtime_has_ten_passed_stages(self) -> None:
        runtime = run_methylation_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 10)
        self.assertTrue(all(stage.status == "passed" for stage in runtime.stages))
        self.assertTrue(runtime.content_address.startswith("sha256:"))

    def test_release_bundle_and_artifact_references_are_addressed(self) -> None:
        runtime = run_methylation_frontier_runtime(fixture=self.fixture)
        release = build_methylation_frontier_release(runtime)
        from glio_noncode.methylation_frontier_artifacts import build_methylation_frontier_artifacts
        from glio_noncode.methylation_frontier_bundle import build_methylation_frontier_bundle

        bundle = build_methylation_frontier_bundle(self.fixture, self.evaluation, release)
        artifacts = build_methylation_frontier_artifacts(runtime.quality, release, bundle)
        self.assertTrue(release.accepted)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertEqual(bundle.record_count, 16)
        self.assertEqual(len(artifacts.artifacts), 4)
        self.assertTrue(bundle.root_address.startswith("sha256:"))

    def test_review_view_and_queue_are_deterministic(self) -> None:
        runtime = run_methylation_frontier_runtime(fixture=self.fixture)
        release = build_methylation_frontier_release(runtime)
        view = build_methylation_frontier_review_view(
            self.fixture, self.evaluation, runtime.policy, release
        )
        queue = build_methylation_frontier_review_queue(view, release)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(view.summary["release_count"], 4)
        self.assertEqual(view.summary["review_count"], 12)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.required_items), 12)
        self.assertEqual(queue.items[0].priority, MethylationFrontierReviewPriority.BLOCKING)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in queue.items))

    def test_observability_carries_stage_and_row_events(self) -> None:
        runtime = run_methylation_frontier_runtime(fixture=self.fixture)
        report = observe_methylation_frontier(runtime)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.events_for("stage_completed")), 10)
        self.assertEqual(len(report.events_for("record_evaluated")), 16)
        self.assertEqual(len(report.by_severity("error")), 0)
        self.assertTrue(all(event.sequence > 0 for event in report.events))

    def test_accessibility_and_invariants_pass(self) -> None:
        accessibility = evaluate_methylation_frontier_accessibility(self.fixture, self.evaluation)
        invariants = run_methylation_frontier_invariants(self.fixture, self.evaluation)
        self.assertTrue(accessibility.accepted)
        self.assertTrue(invariants.accepted)
        self.assertGreaterEqual(accessibility.passed_count, 20)
        self.assertEqual(invariants.failed_ids, ())
        self.assertGreaterEqual(len(invariants.invariants), 20)

    def test_scenario_threshold_and_validation_manifests_pass(self) -> None:
        scenarios = build_methylation_frontier_scenario_matrix()
        thresholds = build_methylation_frontier_threshold_report()
        validation = build_methylation_frontier_validation_matrix()
        self.assertTrue(scenarios.accepted)
        self.assertTrue(thresholds.accepted)
        self.assertTrue(validate_methylation_frontier_matrix(validation))
        self.assertEqual(len(scenarios.scenarios), 32)
        self.assertEqual(len(thresholds.results), 6)
        self.assertEqual(len(validation.cases), 32)

    def test_runbook_and_source_registry_are_complete(self) -> None:
        runbook = default_methylation_frontier_runbook()
        registry = build_methylation_frontier_source_registry(self.fixture)
        self.assertEqual(len(runbook.steps), 18)
        self.assertIn("methylation-frontier-evaluate", runbook.commands())
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.entries), 4)
        self.assertEqual(len(registry.for_context(self.fixture.context_key)), 4)
        self.assertEqual(registry.get("encode-methylation").source_version, "2025.4")

    def test_report_and_exports_are_parseable(self) -> None:
        runtime = run_methylation_frontier_runtime(fixture=self.fixture)
        release = build_methylation_frontier_release(runtime)
        view = build_methylation_frontier_review_view(
            self.fixture, self.evaluation, runtime.policy, release
        )
        report = build_methylation_frontier_report(
            self.fixture, self.evaluation, runtime.metrics, view
        )
        csv_text = export_methylation_frontier_review_rows(view)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        parsed = json.loads(export_methylation_frontier_json(report))
        manifest = export_methylation_frontier_manifest(report, csv_text=csv_text)
        self.assertTrue(report.accepted)
        self.assertEqual(len(rows), 16)
        self.assertEqual(parsed["report_id"], report.report_id)
        self.assertEqual(manifest["fixture_id"], self.fixture.fixture_id)
        self.assertTrue(manifest["manifest_address"].startswith("sha256:"))

    def test_replay_is_stable(self) -> None:
        left = replay_methylation_frontier(self.fixture, replay_id="left")
        right = replay_methylation_frontier(self.fixture, replay_id="right")
        comparison = compare_methylation_frontier_replays(left, right)
        self.assertTrue(comparison.accepted)
        self.assertTrue(methylation_frontier_replay_is_deterministic(self.fixture))

    def test_pipeline_exercises_all_package_surfaces(self) -> None:
        pipeline = run_methylation_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertEqual(len(pipeline.addresses()), 17)
        self.assertTrue(all(value.startswith("sha256:") for value in pipeline.addresses().values()))
        self.assertEqual(pipeline.manifest["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(pipeline.report.section("review").section_id, "review")

    def test_cli_operations_are_json_compatible(self) -> None:
        operations = (
            "methylation-frontier-fixture",
            "methylation-frontier-data",
            "methylation-frontier-evaluate",
            "methylation-frontier-replay",
            "methylation-frontier-quality",
            "methylation-frontier-contracts",
            "methylation-frontier-adapters",
            "methylation-frontier-catalog",
            "methylation-frontier-schema",
            "methylation-frontier-sources",
            "run-methylation-frontier-pipeline",
        )
        for operation in operations:
            with self.subTest(operation=operation):
                payload = run_methylation_frontier_operation(operation)
                encoded = json.dumps(payload, sort_keys=True)
                self.assertTrue(encoded.startswith("{"))
                self.assertIn("content_address", encoded)


if __name__ == "__main__":
    unittest.main()
