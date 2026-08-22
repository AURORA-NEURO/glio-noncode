from __future__ import annotations

import csv
import io
import unittest

from glio_noncode.cell_context_frontier_accessibility import (
    evaluate_cell_context_frontier_accessibility,
)
from glio_noncode.cell_context_frontier_adapters import (
    build_cell_context_frontier_adapters,
    execute_cell_context_frontier_record,
)
from glio_noncode.cell_context_frontier_checks import run_cell_context_frontier_invariants
from glio_noncode.cell_context_frontier_compliance import evaluate_cell_context_frontier_boundary
from glio_noncode.cell_context_frontier_contracts import build_cell_context_frontier_contracts
from glio_noncode.cell_context_frontier_depth import audit_cell_context_frontier_depth
from glio_noncode.cell_context_frontier_exports import (
    export_cell_context_frontier_manifest,
    export_cell_context_frontier_review_csv,
)
from glio_noncode.cell_context_frontier_fixture_eval import evaluate_cell_context_frontier_fixture
from glio_noncode.cell_context_frontier_integrity import evaluate_cell_context_frontier_integrity
from glio_noncode.cell_context_frontier_metrics import build_cell_context_frontier_metrics
from glio_noncode.cell_context_frontier_observability import build_cell_context_frontier_trace
from glio_noncode.cell_context_frontier_pipeline import run_cell_context_frontier_pipeline
from glio_noncode.cell_context_frontier_policy import evaluate_cell_context_frontier_policy
from glio_noncode.cell_context_frontier_public_data import (
    CELL_CONTEXT_FRONTIER_BOUNDARY,
    CELL_CONTEXT_FRONTIER_CONTEXT_KEY,
    CellContextFrontierExpectedState,
    CellContextFrontierOperation,
    audit_cell_context_frontier_data,
    default_cell_context_frontier_fixture,
)
from glio_noncode.cell_context_frontier_release import build_cell_context_frontier_release
from glio_noncode.cell_context_frontier_replay import replay_cell_context_frontier
from glio_noncode.cell_context_frontier_review_queue import build_cell_context_frontier_review_queue
from glio_noncode.cell_context_frontier_runbook import default_cell_context_frontier_runbook
from glio_noncode.cell_context_frontier_runtime import run_cell_context_frontier_runtime
from glio_noncode.cell_context_frontier_scenario_matrix import (
    build_cell_context_frontier_scenario_matrix,
    evaluate_cell_context_frontier_scenarios,
)
from glio_noncode.cell_context_frontier_schema import validate_cell_context_frontier_schema
from glio_noncode.cell_context_frontier_source_registry import (
    build_cell_context_frontier_source_registry,
)
from glio_noncode.cell_context_frontier_thresholds import (
    build_cell_context_frontier_threshold_report,
)
from glio_noncode.cell_context_frontier_validation_matrix import (
    build_cell_context_frontier_validation_matrix,
    validate_cell_context_frontier_matrix,
)
from glio_noncode.cell_context_frontier_views import build_cell_context_frontier_view
from glio_noncode.errors import ValidationError


class CellContextFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_cell_context_frontier_fixture()

    def test_fixture_counts_and_boundary(self) -> None:
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(self.fixture.context_key, CELL_CONTEXT_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, CELL_CONTEXT_FRONTIER_BOUNDARY)
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))

    def test_data_audit_passes(self) -> None:
        audit = audit_cell_context_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertFalse(audit.failed_check_ids)
        self.assertEqual(len(audit.checks), 10)

    def test_operation_balance_is_four_rows_each(self) -> None:
        for operation in CellContextFrontierOperation:
            rows = self.fixture.operation_records(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role.value == "positive" for item in rows), 1)

    def test_fixture_evaluation_reconciles_every_expected_state(self) -> None:
        evaluation = evaluate_cell_context_frontier_fixture(self.fixture)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(evaluation.state_match_count, 16)
        self.assertEqual(evaluation.issue_match_count, 16)
        self.assertEqual({item.observed_state for item in evaluation.positive_rows}, {"supported"})
        controls = {item.observed_state for item in evaluation.control_rows}
        self.assertTrue(
            {"partial", "ambiguous", "contradictory", "out_of_domain", "abstained"} <= controls
        )

    def test_adapter_registry_covers_four_primitives(self) -> None:
        registry = build_cell_context_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        self.assertEqual(
            {item.operation for item in registry.specs}, set(CellContextFrontierOperation)
        )
        self.assertTrue(all(item.limitations for item in registry.specs))

    def test_all_adapter_results_have_receipts_and_limits(self) -> None:
        for record in self.fixture.records:
            result = execute_cell_context_frontier_record(record)
            self.assertEqual(result.record_id, record.record_id)
            self.assertTrue(result.content_address.startswith("sha256:"))
            self.assertTrue(result.warnings)

    def test_contracts_retain_refusal_paths(self) -> None:
        report = build_cell_context_frontier_contracts()
        self.assertTrue(report.accepted)
        self.assertEqual(report.unique_operations, 4)
        self.assertTrue(all("context_mismatch" in item.refusal_paths for item in report.contracts))

    def test_schema_passes_with_evaluation(self) -> None:
        evaluation = evaluate_cell_context_frontier_fixture(self.fixture)
        report = validate_cell_context_frontier_schema(self.fixture, evaluation)
        self.assertTrue(report.accepted)
        self.assertFalse(report.failed_check_ids)

    def test_runtime_has_ten_passed_stages(self) -> None:
        runtime = run_cell_context_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 10)
        self.assertFalse(runtime.failed_stages)
        self.assertFalse(runtime.quality.failed_check_ids)

    def test_runtime_rejects_context_drift(self) -> None:
        from glio_noncode.cell_context_frontier_runtime import CellContextFrontierRuntimeOptions

        with self.assertRaises(ValidationError):
            run_cell_context_frontier_runtime(
                CellContextFrontierRuntimeOptions(
                    context_key="GRCh38|glioma|pediatric|stem_like|core|unknown"
                ),
                fixture=self.fixture,
            )

    def test_metrics_meet_all_floors(self) -> None:
        evaluation = evaluate_cell_context_frontier_fixture(self.fixture)
        metrics = build_cell_context_frontier_metrics(evaluation)
        self.assertTrue(metrics.accepted)
        self.assertFalse(metrics.failed_metric_ids)
        self.assertGreaterEqual(len(metrics.metrics), 10)

    def test_policy_has_release_review_and_refusal(self) -> None:
        evaluation = evaluate_cell_context_frontier_fixture(self.fixture)
        policy = evaluate_cell_context_frontier_policy(evaluation)
        self.assertTrue(policy.accepted)
        self.assertEqual(policy.release_count, 4)
        self.assertGreaterEqual(policy.review_count, 1)
        self.assertGreaterEqual(policy.refusal_count, 1)

    def test_lineage_reaches_all_records(self) -> None:
        runtime = run_cell_context_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.lineage.accepted)
        self.assertEqual(runtime.lineage.record_count, 16)
        self.assertEqual(runtime.lineage.source_count, 5)
        self.assertTrue(
            all(runtime.lineage.for_record(item.record_id) for item in self.fixture.records)
        )

    def test_reconciliation_has_no_mismatches(self) -> None:
        runtime = run_cell_context_frontier_runtime(fixture=self.fixture)
        self.assertTrue(runtime.reconciliation.accepted)
        self.assertEqual(runtime.reconciliation.matched_count, 16)
        self.assertFalse(runtime.reconciliation.mismatch_ids)

    def test_release_manifest_is_candidate_and_limited(self) -> None:
        runtime = run_cell_context_frontier_runtime(fixture=self.fixture)
        release = build_cell_context_frontier_release(runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(release.release_status, "release_candidate")
        self.assertEqual(len(release.supported_operations), 4)
        self.assertTrue(release.refusal_paths)
        self.assertTrue(release.review_paths)
        self.assertGreaterEqual(len(release.limitations), 3)

    def test_source_registry_has_five_receipts(self) -> None:
        registry = build_cell_context_frontier_source_registry(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.entries), 5)
        self.assertEqual(sum(item.operation_count for item in registry.entries), 16)

    def test_review_view_and_queue_retain_controls(self) -> None:
        runtime = run_cell_context_frontier_runtime(fixture=self.fixture)
        release = build_cell_context_frontier_release(runtime)
        view = build_cell_context_frontier_view(
            self.fixture, runtime.evaluation, runtime.policy, release
        )
        queue = build_cell_context_frontier_review_queue(view, release)
        self.assertTrue(view.accepted)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(view.release_rows), 4)
        self.assertEqual(len(queue.items), 12)
        self.assertGreaterEqual(queue.blocking_count, 1)
        self.assertGreaterEqual(queue.advisory_count, 1)
        self.assertEqual(queue.items[0].priority, "critical")

    def test_boundary_and_invariants_pass(self) -> None:
        evaluation = evaluate_cell_context_frontier_fixture(self.fixture)
        boundary = evaluate_cell_context_frontier_boundary(self.fixture, evaluation)
        invariants = run_cell_context_frontier_invariants(self.fixture, evaluation)
        self.assertTrue(boundary.accepted)
        self.assertTrue(invariants.accepted)
        self.assertFalse(boundary.failed_check_ids)
        self.assertFalse(invariants.failed_ids)

    def test_scenarios_have_twelve_passed_rows(self) -> None:
        matrix = evaluate_cell_context_frontier_scenarios(
            build_cell_context_frontier_scenario_matrix()
        )
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertTrue(all(item.passed for item in matrix.results))

    def test_thresholds_and_validation_matrix_pass(self) -> None:
        thresholds = build_cell_context_frontier_threshold_report()
        matrix = build_cell_context_frontier_validation_matrix()
        self.assertTrue(thresholds.accepted)
        self.assertEqual(len(thresholds.thresholds), 10)
        self.assertEqual(len(matrix.cells), 24)
        self.assertTrue(validate_cell_context_frontier_matrix(matrix))

    def test_runbook_has_ten_steps(self) -> None:
        runbook = default_cell_context_frontier_runbook()
        self.assertTrue(runbook.accepted)
        self.assertEqual(len(runbook.steps), 10)
        self.assertTrue(runbook.phase("execute"))
        self.assertGreaterEqual(len(runbook.escalation_rules), 4)

    def test_replay_is_deterministic(self) -> None:
        replay = replay_cell_context_frontier(self.fixture)
        self.assertTrue(replay.accepted)
        self.assertTrue(replay.deterministic)
        self.assertEqual(replay.first_result_address, replay.second_result_address)

    def test_trace_has_ten_events(self) -> None:
        runtime = run_cell_context_frontier_runtime(fixture=self.fixture)
        trace = build_cell_context_frontier_trace(runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events), 10)
        self.assertEqual(trace.counters["record_count"], 16)
        self.assertEqual(trace.event("quality_gate").status, "passed")

    def test_pipeline_is_accepted(self) -> None:
        pipeline = run_cell_context_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertTrue(pipeline.accessibility.accepted)
        self.assertTrue(pipeline.depth.accepted)
        self.assertTrue(pipeline.integrity.accepted)
        self.assertGreaterEqual(pipeline.depth.mean_score, 0.75)
        self.assertTrue(pipeline.bundle.accepted)
        self.assertTrue(pipeline.artifacts.accepted)
        self.assertEqual(len(pipeline.review_queue.items), 12)
        self.assertEqual(len(pipeline.report.sections), 6)
        self.assertTrue(pipeline.manifest["review_csv"]["row_count"] == 16)

    def test_csv_export_is_parseable(self) -> None:
        pipeline = run_cell_context_frontier_pipeline(self.fixture)
        text = export_cell_context_frontier_review_csv(pipeline.review_view)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(len(rows), 16)
        self.assertIn("d08-c01-positive", {item["record_id"] for item in rows})
        manifest = export_cell_context_frontier_manifest(pipeline.report, csv_text=text)
        self.assertEqual(manifest["review_csv"]["row_count"], 16)

    def test_expected_state_paths_are_explicit(self) -> None:
        self.assertEqual(
            {item.value for item in CellContextFrontierExpectedState},
            {"supported", "partial", "ambiguous", "contradictory", "out_of_domain", "abstained"},
        )

    def test_depth_accessibility_and_integrity_surfaces_pass(self) -> None:
        evaluation = evaluate_cell_context_frontier_fixture(self.fixture)
        accessibility = evaluate_cell_context_frontier_accessibility(evaluation)
        depth = audit_cell_context_frontier_depth(evaluation)
        integrity = evaluate_cell_context_frontier_integrity(self.fixture, evaluation)
        self.assertTrue(accessibility.accepted)
        self.assertEqual(accessibility.available_operation_count, 4)
        self.assertTrue(depth.accepted)
        self.assertEqual(len(depth.dimensions), 4)
        self.assertTrue(integrity.accepted)
        self.assertEqual(integrity.error_count, 0)


if __name__ == "__main__":
    unittest.main()
