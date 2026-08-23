from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.control_frontier_access import audit_control_frontier_access, build_control_frontier_access_manifest
from glio_noncode.control_frontier_adapters import build_control_frontier_adapters
from glio_noncode.control_frontier_audit_log import build_control_frontier_audit_log, verify_control_frontier_audit_log
from glio_noncode.control_frontier_benchmark import run_control_frontier_benchmark
from glio_noncode.control_frontier_claim_boundary import evaluate_control_frontier_claim_boundary
from glio_noncode.control_frontier_contracts import CONTROL_FRONTIER_CONTEXT_KEY, ControlFrontierOperation, ControlFrontierRole, ControlFrontierState
from glio_noncode.control_frontier_depth import audit_control_frontier_depth
from glio_noncode.control_frontier_diagnostics import diagnose_control_frontier
from glio_noncode.control_frontier_evidence_matrix import build_control_frontier_evidence_matrix
from glio_noncode.control_frontier_exports import export_control_frontier_json, export_control_frontier_metrics_csv, export_control_frontier_review_csv, render_control_frontier_review_markdown
from glio_noncode.control_frontier_failure_injection import run_control_frontier_failure_injections
from glio_noncode.control_frontier_fixture_eval import evaluate_control_frontier_fixture, execute_control_frontier_record
from glio_noncode.control_frontier_handoff import build_control_frontier_handoff
from glio_noncode.control_frontier_integrity import evaluate_control_frontier_integrity
from glio_noncode.control_frontier_lineage import build_control_frontier_lineage, verify_control_frontier_lineage
from glio_noncode.control_frontier_metrics import measure_control_frontier
from glio_noncode.control_frontier_operational import build_control_frontier_operational_matrix
from glio_noncode.control_frontier_package import build_control_frontier_package_manifest
from glio_noncode.control_frontier_performance import build_control_frontier_performance_budget
from glio_noncode.control_frontier_policy import default_control_frontier_policy
from glio_noncode.control_frontier_projection_assertions import assert_control_frontier_projection
from glio_noncode.control_frontier_public_data import audit_control_frontier_data, default_control_frontier_fixture
from glio_noncode.control_frontier_quality_gate import run_control_frontier_quality_gate
from glio_noncode.control_frontier_reconciliation import reconcile_control_frontier
from glio_noncode.control_frontier_recovery import build_control_frontier_recovery_plan
from glio_noncode.control_frontier_release import build_control_frontier_release
from glio_noncode.control_frontier_replay import replay_control_frontier_evaluation
from glio_noncode.control_frontier_review_queue import build_control_frontier_review_queue
from glio_noncode.control_frontier_review_sla import build_control_frontier_review_sla
from glio_noncode.control_frontier_runbook import build_control_frontier_runbook
from glio_noncode.control_frontier_runtime import run_control_frontier_runtime
from glio_noncode.control_frontier_scenario_matrix import evaluate_control_frontier_scenarios
from glio_noncode.control_frontier_schema import default_control_frontier_schema, validate_control_frontier_schema
from glio_noncode.control_frontier_source_registry import build_control_frontier_source_registry
from glio_noncode.control_frontier_summary import build_control_frontier_summary
from glio_noncode.control_frontier_support import default_control_frontier_support_directory
from glio_noncode.control_frontier_thresholds import build_control_frontier_threshold_report, validate_control_frontier_threshold_report
from glio_noncode.control_frontier_validation_matrix import build_control_frontier_validation_matrix, validate_control_frontier_matrix
from glio_noncode.control_frontier_views import build_control_frontier_view


class ControlFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_control_frontier_fixture()
        self.audit = audit_control_frontier_data(self.fixture)
        self.evaluation = evaluate_control_frontier_fixture(self.fixture)
        self.metrics = measure_control_frontier(self.evaluation)

    def test_public_fixture_has_exact_aggregate_cardinality(self) -> None:
        self.assertEqual(self.fixture.context_key, CONTROL_FRONTIER_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.sources), 9)
        self.assertEqual(len(self.fixture.records), 32)
        self.assertEqual(len(self.fixture.positive_records), 8)
        self.assertEqual(len(self.fixture.control_records), 24)
        self.assertTrue(self.audit.accepted)

    def test_evaluation_executes_all_operations_and_controls(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 32)
        self.assertEqual(len(self.evaluation.checks), 160)
        self.assertEqual(self.evaluation.passed_checks, 160)
        self.assertEqual(sum(item.accepted for item in self.evaluation.executions), 8)
        self.assertEqual(self.evaluation.failed_check_ids, ())

    def test_each_operation_has_one_positive_and_three_controls(self) -> None:
        for operation in ControlFrontierOperation:
            rows = self.evaluation.by_operation(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role is ControlFrontierRole.POSITIVE for item in rows), 1)
            self.assertEqual(sum(item.role is ControlFrontierRole.CONTROL for item in rows), 3)

    def test_control_states_are_not_promoted_to_acceptance(self) -> None:
        self.assertTrue(all(not item.accepted for item in self.evaluation.executions if item.role is ControlFrontierRole.CONTROL))
        self.assertEqual(self.evaluation.by_operation(ControlFrontierOperation.POLICY_CLAIM_GATE)[1].state, ControlFrontierState.BLOCKED)
        self.assertEqual(self.evaluation.by_operation(ControlFrontierOperation.DRIFT_OOD_MONITOR)[3].state, ControlFrontierState.OUT_OF_DOMAIN)

    def test_operation_receipts_are_addressed(self) -> None:
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.evaluation.executions))
        self.assertEqual(len({item.content_address for item in self.evaluation.executions}), 32)

    def test_adapters_cover_all_eight_operations(self) -> None:
        registry = build_control_frontier_adapters()
        self.assertEqual(len(registry.specs), 8)
        self.assertEqual({item.operation for item in registry.specs}, set(ControlFrontierOperation))
        self.assertTrue(all(item.deterministic for item in registry.specs))

    def test_schema_is_complete(self) -> None:
        schema = default_control_frontier_schema()
        self.assertEqual(validate_control_frontier_schema(schema), ())
        self.assertGreaterEqual(schema.field_count, 16)

    def test_reconciliation_and_quality_gate_are_green(self) -> None:
        adapters = build_control_frontier_adapters()
        schema = default_control_frontier_schema()
        policy = default_control_frontier_policy()
        lineage = build_control_frontier_lineage(self.fixture, self.evaluation)
        reconciliation = reconcile_control_frontier(self.fixture, self.evaluation)
        quality = run_control_frontier_quality_gate(self.fixture, self.audit, self.evaluation, self.metrics, adapters, schema, policy, lineage, reconciliation)
        self.assertTrue(reconciliation.reconciled)
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.blockers, ())

    def test_replay_is_deterministic(self) -> None:
        replay = replay_control_frontier_evaluation(self.fixture, self.evaluation)
        self.assertTrue(replay.deterministic)
        self.assertEqual(len(replay.checks), 32)

    def test_lineage_closes_source_and_execution_nodes(self) -> None:
        lineage = build_control_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertEqual(verify_control_frontier_lineage(lineage), ())
        self.assertEqual(len(lineage.edges), 64)

    def test_depth_audit_covers_all_secondary_surfaces(self) -> None:
        depth = audit_control_frontier_depth(self.fixture, self.evaluation)
        self.assertTrue(depth.accepted)
        self.assertEqual(len(depth.checks), 8)

    def test_runtime_is_accepted_and_stage_complete(self) -> None:
        runtime = run_control_frontier_runtime(self.fixture, run_id="control-frontier-test")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 24)
        self.assertTrue(runtime.depth.accepted)
        self.assertEqual(runtime.stage_ids[0], "data-audit")
        self.assertEqual(runtime.stage_ids[-1], "depth")

    def test_release_bundle_and_package_are_closed(self) -> None:
        runtime = run_control_frontier_runtime(self.fixture, run_id="control-frontier-package")
        release = runtime.release
        self.assertTrue(release.accepted)
        inventory = runtime.artifacts
        self.assertTrue(inventory.complete)
        package = build_control_frontier_package_manifest(inventory, release)
        self.assertTrue(package.accepted)
        self.assertGreaterEqual(len(package.files), 8)

    def test_review_queue_and_sla_keep_controls_actionable(self) -> None:
        queue = build_control_frontier_review_queue(self.evaluation, max_items=12)
        sla = build_control_frontier_review_sla(self.evaluation)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.items), 12)
        self.assertEqual(len(queue.omitted_record_ids), 12)
        self.assertTrue(sla.accepted)
        self.assertEqual(len(sla.rows), 32)

    def test_source_registry_and_access_manifest_are_public(self) -> None:
        registry = build_control_frontier_source_registry(self.fixture)
        manifest = build_control_frontier_access_manifest(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertTrue(manifest.accepted)
        self.assertEqual(audit_control_frontier_access(manifest), ())
        self.assertEqual(len(manifest.surfaces), 6)

    def test_projection_exports_have_stable_headers(self) -> None:
        view = build_control_frontier_view(self.evaluation)
        self.assertTrue(export_control_frontier_json(self.evaluation).startswith("{"))
        self.assertEqual(export_control_frontier_review_csv(view).splitlines()[0], "record_id,operation,role,state,accepted,issue_codes")
        self.assertEqual(export_control_frontier_metrics_csv(self.evaluation).splitlines()[0], "record_id,operation,state,accepted,issue_count")
        self.assertIn("# Control frontier review", render_control_frontier_review_markdown(view))
        self.assertTrue(assert_control_frontier_projection(self.evaluation).accepted)

    def test_operational_support_runbook_and_recovery_surfaces(self) -> None:
        self.assertTrue(build_control_frontier_operational_matrix().accepted)
        self.assertTrue(build_control_frontier_runbook().accepted)
        self.assertTrue(build_control_frontier_recovery_plan().accepted)
        self.assertTrue(default_control_frontier_support_directory().accepted)
        self.assertEqual(len(build_control_frontier_performance_budget()), 8)

    def test_failure_injection_detects_declared_mutations(self) -> None:
        report = run_control_frontier_failure_injections(self.fixture)
        self.assertTrue(report.accepted)
        self.assertTrue(all(item.detected for item in report.injections))

    def test_claim_boundary_and_diagnostics_are_explicit(self) -> None:
        boundary = evaluate_control_frontier_claim_boundary(self.evaluation)
        diagnostics = diagnose_control_frontier(self.evaluation)
        self.assertTrue(boundary.accepted)
        self.assertTrue(diagnostics.accepted)
        self.assertGreater(len(diagnostics.findings), 0)

    def test_threshold_and_validation_surfaces_have_fixed_cardinality(self) -> None:
        thresholds = build_control_frontier_threshold_report()
        matrix = build_control_frontier_validation_matrix(self.evaluation)
        evidence = build_control_frontier_evidence_matrix(self.evaluation)
        self.assertEqual(thresholds.probe_count, 32)
        self.assertEqual(validate_control_frontier_threshold_report(thresholds), ())
        self.assertEqual(matrix.cell_count, 128)
        self.assertEqual(validate_control_frontier_matrix(matrix), ())
        self.assertEqual(len(evidence.cells), 192)
        self.assertTrue(evidence.accepted)

    def test_summary_and_handoff_retain_operation_counts(self) -> None:
        runtime = run_control_frontier_runtime(self.fixture, run_id="control-frontier-summary")
        summary = build_control_frontier_summary(self.fixture, self.evaluation, self.metrics, runtime.quality)
        handoff = build_control_frontier_handoff(self.fixture, self.evaluation, self.metrics)
        self.assertEqual(summary.operation_count, 8)
        self.assertEqual(summary.record_count, 32)
        self.assertTrue(handoff.accepted)
        self.assertEqual(len(handoff.items), 8)

    def test_audit_log_replays_all_runtime_stages(self) -> None:
        runtime = run_control_frontier_runtime(self.fixture, run_id="control-frontier-audit")
        log = build_control_frontier_audit_log(runtime.run_id, runtime.stages)
        accepted, issues = verify_control_frontier_audit_log(log.events)
        self.assertTrue(log.accepted)
        self.assertTrue(accepted)
        self.assertEqual(issues, ())
        self.assertEqual(len(log.events), 24)

    def test_benchmark_is_a_positive_regression_signal(self) -> None:
        report = run_control_frontier_benchmark(self.fixture, repetitions=1)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.samples), 2)

    def test_fixture_payload_mutation_is_visible(self) -> None:
        original = self.fixture.records[0]
        changed = replace(original, notes=original.notes + " changed")
        self.assertNotEqual(original.to_dict()["notes"], changed.to_dict()["notes"])


if __name__ == "__main__":
    unittest.main()
