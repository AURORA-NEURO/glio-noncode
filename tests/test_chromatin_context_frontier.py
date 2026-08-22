from __future__ import annotations

import csv
import io
import unittest

from glio_noncode.chromatin_context_frontier_adapters import (
    build_chromatin_context_frontier_adapters,
    execute_chromatin_context_frontier_record,
)
from glio_noncode.chromatin_context_frontier_checks import run_chromatin_context_frontier_invariants
from glio_noncode.chromatin_context_frontier_compliance import (
    evaluate_chromatin_context_frontier_boundary,
)
from glio_noncode.chromatin_context_frontier_contracts import (
    build_chromatin_context_frontier_contracts,
)
from glio_noncode.chromatin_context_frontier_exports import (
    export_chromatin_context_frontier_manifest,
    export_chromatin_context_frontier_review_csv,
)
from glio_noncode.chromatin_context_frontier_fixture_eval import (
    evaluate_chromatin_context_frontier_fixture,
)
from glio_noncode.chromatin_context_frontier_metrics import build_chromatin_context_frontier_metrics
from glio_noncode.chromatin_context_frontier_observability import (
    build_chromatin_context_frontier_trace,
)
from glio_noncode.chromatin_context_frontier_pipeline import run_chromatin_context_frontier_pipeline
from glio_noncode.chromatin_context_frontier_policy import (
    evaluate_chromatin_context_frontier_policy,
)
from glio_noncode.chromatin_context_frontier_public_data import (
    CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
    CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY,
    ChromatinContextFrontierExpectedState,
    ChromatinContextFrontierOperation,
    audit_chromatin_context_frontier_data,
    default_chromatin_context_frontier_fixture,
)
from glio_noncode.chromatin_context_frontier_reconciliation import (
    reconcile_chromatin_context_frontier,
)
from glio_noncode.chromatin_context_frontier_release import build_chromatin_context_frontier_release
from glio_noncode.chromatin_context_frontier_replay import replay_chromatin_context_frontier
from glio_noncode.chromatin_context_frontier_review_queue import (
    build_chromatin_context_frontier_review_queue,
)
from glio_noncode.chromatin_context_frontier_runbook import (
    default_chromatin_context_frontier_runbook,
)
from glio_noncode.chromatin_context_frontier_runtime import run_chromatin_context_frontier_runtime
from glio_noncode.chromatin_context_frontier_scenario_matrix import (
    build_chromatin_context_frontier_scenario_matrix,
    evaluate_chromatin_context_frontier_scenarios,
)
from glio_noncode.chromatin_context_frontier_schema import (
    validate_chromatin_context_frontier_schema,
)
from glio_noncode.chromatin_context_frontier_source_registry import (
    build_chromatin_context_frontier_source_registry,
)
from glio_noncode.chromatin_context_frontier_thresholds import (
    build_chromatin_context_frontier_threshold_report,
)
from glio_noncode.chromatin_context_frontier_validation_matrix import (
    build_chromatin_context_frontier_validation_matrix,
    validate_chromatin_context_frontier_matrix,
)
from glio_noncode.chromatin_context_frontier_views import build_chromatin_context_frontier_view
from glio_noncode.errors import ValidationError


class ChromatinContextFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_chromatin_context_frontier_fixture()

    def test_fixture_has_four_positive_and_twelve_controls(self) -> None:
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(self.fixture.context_key, CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, CHROMATIN_CONTEXT_FRONTIER_BOUNDARY)
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))

    def test_fixture_audit_passes_all_data_checks(self) -> None:
        audit = audit_chromatin_context_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertFalse(audit.failed_check_ids)
        self.assertEqual(len(audit.checks), 10)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in audit.checks))

    def test_fixture_covers_each_operation_evenly(self) -> None:
        for operation in ChromatinContextFrontierOperation:
            rows = self.fixture.operation_records(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(row.role.value == "positive" for row in rows), 1)

    def test_all_records_execute_to_expected_states(self) -> None:
        evaluation = evaluate_chromatin_context_frontier_fixture(self.fixture)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(evaluation.state_match_count, 16)
        self.assertEqual(evaluation.issue_match_count, 16)
        self.assertEqual({row.observed_state for row in evaluation.positive_rows}, {"supported"})
        self.assertIn("out_of_domain", {row.observed_state for row in evaluation.control_rows})
        self.assertIn("ambiguous", {row.observed_state for row in evaluation.control_rows})
        self.assertIn("partial", {row.observed_state for row in evaluation.control_rows})
        self.assertIn("abstained", {row.observed_state for row in evaluation.control_rows})

    def test_adapter_registry_covers_all_operations(self) -> None:
        registry = build_chromatin_context_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        self.assertEqual(
            {item.operation for item in registry.specs}, set(ChromatinContextFrontierOperation)
        )
        for item in registry.specs:
            self.assertTrue(item.content_address.startswith("sha256:"))
            self.assertTrue(item.required_fields)
            self.assertTrue(item.limitations)

    def test_individual_adapter_results_have_receipts(self) -> None:
        for record in self.fixture.records:
            result = execute_chromatin_context_frontier_record(record)
            self.assertEqual(result.record_id, record.record_id)
            self.assertTrue(result.content_address.startswith("sha256:"))
            self.assertTrue(result.detail)
            self.assertTrue(result.warnings)

    def test_contracts_have_refusal_paths(self) -> None:
        report = build_chromatin_context_frontier_contracts()
        self.assertTrue(report.accepted)
        self.assertEqual(report.unique_operations, 4)
        for contract in report.contracts:
            self.assertIn("context_mismatch", contract.refusal_paths)
            self.assertTrue(contract.output_shape)

    def test_schema_report_accepts_fixture_and_evaluation(self) -> None:
        evaluation = evaluate_chromatin_context_frontier_fixture(self.fixture)
        report = validate_chromatin_context_frontier_schema(self.fixture, evaluation)
        self.assertTrue(report.accepted)
        self.assertFalse(report.failed_check_ids)
        self.assertGreaterEqual(len(report.checks), 9)

    def test_runtime_has_ten_passed_stages(self) -> None:
        runtime = run_chromatin_context_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 10)
        self.assertFalse(runtime.failed_stages)
        self.assertTrue(runtime.quality.accepted)
        self.assertFalse(runtime.quality.failed_check_ids)

    def test_runtime_rejects_context_drift_in_options(self) -> None:
        from glio_noncode.chromatin_context_frontier_runtime import (
            ChromatinContextFrontierRuntimeOptions,
        )

        with self.assertRaises(ValidationError):
            run_chromatin_context_frontier_runtime(
                ChromatinContextFrontierRuntimeOptions(
                    context_key="GRCh38|glioma|adult|cycling|tumor|unknown"
                ),
                fixture=self.fixture,
            )

    def test_metrics_have_no_failed_floors(self) -> None:
        evaluation = evaluate_chromatin_context_frontier_fixture(self.fixture)
        metrics = build_chromatin_context_frontier_metrics(evaluation)
        self.assertTrue(metrics.accepted)
        self.assertFalse(metrics.failed_metric_ids)
        self.assertGreaterEqual(len(metrics.metrics), 8)

    def test_policy_separates_release_review_and_refusal(self) -> None:
        evaluation = evaluate_chromatin_context_frontier_fixture(self.fixture)
        policy = evaluate_chromatin_context_frontier_policy(evaluation)
        self.assertTrue(policy.accepted)
        self.assertEqual(policy.release_count, 4)
        self.assertGreaterEqual(policy.review_count, 1)
        self.assertGreaterEqual(policy.refusal_count, 1)
        self.assertEqual(len(policy.decisions), 16)

    def test_reconciliation_is_exact(self) -> None:
        evaluation = evaluate_chromatin_context_frontier_fixture(self.fixture)
        reconciliation = reconcile_chromatin_context_frontier(evaluation)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.matched_count, 16)
        self.assertFalse(reconciliation.mismatch_ids)

    def test_lineage_links_every_record(self) -> None:
        runtime = run_chromatin_context_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.lineage.accepted)
        self.assertEqual(runtime.lineage.record_count, 16)
        self.assertEqual(runtime.lineage.source_count, 5)
        for record in self.fixture.records:
            self.assertTrue(runtime.lineage.for_record(record.record_id))

    def test_release_manifest_retains_limits(self) -> None:
        runtime = run_chromatin_context_frontier_runtime(fixture=self.fixture)
        release = build_chromatin_context_frontier_release(runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(release.release_status, "release_candidate")
        self.assertEqual(len(release.supported_operations), 4)
        self.assertTrue(release.refusal_paths)
        self.assertTrue(release.review_paths)
        self.assertGreaterEqual(len(release.limitations), 3)

    def test_source_registry_retains_all_five_receipts(self) -> None:
        registry = build_chromatin_context_frontier_source_registry(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.entries), 5)
        self.assertEqual(sum(item.operation_count for item in registry.entries), 16)
        self.assertTrue(all(item.receipt.public_aggregate for item in registry.entries))

    def test_view_and_queue_retain_non_release_paths(self) -> None:
        runtime = run_chromatin_context_frontier_runtime(fixture=self.fixture)
        release = build_chromatin_context_frontier_release(runtime)
        view = build_chromatin_context_frontier_view(
            self.fixture, runtime.evaluation, runtime.policy, release
        )
        queue = build_chromatin_context_frontier_review_queue(view, release)
        self.assertTrue(view.accepted)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(view.release_rows), 4)
        self.assertEqual(len(queue.items), 12)
        self.assertGreaterEqual(queue.blocking_count, 1)
        self.assertGreaterEqual(queue.advisory_count, 1)
        self.assertEqual(queue.items[0].priority, "critical")

    def test_boundary_and_invariants_pass(self) -> None:
        evaluation = evaluate_chromatin_context_frontier_fixture(self.fixture)
        boundary = evaluate_chromatin_context_frontier_boundary(self.fixture, evaluation)
        invariants = run_chromatin_context_frontier_invariants(self.fixture, evaluation)
        self.assertTrue(boundary.accepted)
        self.assertTrue(invariants.accepted)
        self.assertFalse(boundary.failed_check_ids)
        self.assertFalse(invariants.failed_ids)

    def test_scenario_matrix_has_twelve_passed_scenarios(self) -> None:
        matrix = build_chromatin_context_frontier_scenario_matrix()
        evaluated = evaluate_chromatin_context_frontier_scenarios(matrix)
        self.assertTrue(evaluated.accepted)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertEqual(len(evaluated.results), 12)
        self.assertTrue(all(item.passed for item in evaluated.results))

    def test_thresholds_and_validation_matrix_are_stable(self) -> None:
        thresholds = build_chromatin_context_frontier_threshold_report()
        matrix = build_chromatin_context_frontier_validation_matrix()
        self.assertTrue(thresholds.accepted)
        self.assertEqual(len(thresholds.thresholds), 10)
        self.assertEqual(len(matrix.cells), 24)
        self.assertTrue(validate_chromatin_context_frontier_matrix(matrix))

    def test_runbook_has_ten_steps_and_escalation_rules(self) -> None:
        runbook = default_chromatin_context_frontier_runbook()
        self.assertTrue(runbook.accepted)
        self.assertEqual(len(runbook.steps), 10)
        self.assertGreaterEqual(len(runbook.escalation_rules), 4)
        self.assertTrue(runbook.phase("execute"))

    def test_replay_is_deterministic(self) -> None:
        receipt = replay_chromatin_context_frontier(self.fixture)
        self.assertTrue(receipt.accepted)
        self.assertTrue(receipt.deterministic)
        self.assertEqual(receipt.first_result_address, receipt.second_result_address)
        self.assertEqual(receipt.checked_record_count, 16)

    def test_observability_has_one_event_per_stage(self) -> None:
        runtime = run_chromatin_context_frontier_runtime(fixture=self.fixture)
        trace = build_chromatin_context_frontier_trace(runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events), 10)
        self.assertEqual(trace.counters["record_count"], 16)
        self.assertEqual(trace.event("quality_gate").status, "passed")

    def test_pipeline_builds_bundle_artifacts_and_manifest(self) -> None:
        pipeline = run_chromatin_context_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertTrue(pipeline.bundle.accepted)
        self.assertTrue(pipeline.artifacts.accepted)
        self.assertEqual(len(pipeline.artifacts.artifacts), 7)
        self.assertEqual(len(pipeline.report.sections), 5)
        self.assertIn("review_csv", pipeline.manifest)
        self.assertTrue(pipeline.content_address.startswith("sha256:"))

    def test_exports_have_expected_csv_rows(self) -> None:
        pipeline = run_chromatin_context_frontier_pipeline(self.fixture)
        csv_text = export_chromatin_context_frontier_review_csv(pipeline.review_view)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[0]["record_id"], "d07-c01-positive")
        manifest = export_chromatin_context_frontier_manifest(pipeline.report, csv_text=csv_text)
        self.assertEqual(manifest["review_csv"]["row_count"], 16)

    def test_expected_state_enum_has_six_paths(self) -> None:
        self.assertEqual(
            set(item.value for item in ChromatinContextFrontierExpectedState),
            {"supported", "partial", "ambiguous", "out_of_domain", "abstained", "invalid"},
        )


if __name__ == "__main__":
    unittest.main()
