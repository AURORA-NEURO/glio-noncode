"""Deep evidence tests for Domain 12 C01-C04."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_foundation_frontier_adapters import default_cohort_foundation_frontier_adapters
from glio_noncode.cohort_foundation_frontier_accessibility import build_cohort_foundation_frontier_accessibility_report
from glio_noncode.cohort_foundation_frontier_audit_log import build_cohort_foundation_frontier_audit_log
from glio_noncode.cohort_foundation_frontier_claim_evidence import build_cohort_foundation_frontier_claim_evidence_ledger
from glio_noncode.cohort_foundation_frontier_change_control import default_cohort_foundation_frontier_change_control_report
from glio_noncode.cohort_foundation_frontier_compatibility import evaluate_cohort_foundation_frontier_compatibility
from glio_noncode.cohort_foundation_frontier_artifacts import CohortFoundationArtifactKind
from glio_noncode.cohort_foundation_frontier_assurance import build_cohort_foundation_frontier_assurance
from glio_noncode.cohort_foundation_frontier_claim_boundary import build_cohort_foundation_frontier_claim_boundary
from glio_noncode.cohort_foundation_frontier_checks import cohort_foundation_frontier_observation_map, default_cohort_foundation_frontier_invariants, run_cohort_foundation_frontier_invariants
from glio_noncode.cohort_foundation_frontier_control_coverage import build_cohort_foundation_frontier_control_coverage
from glio_noncode.cohort_foundation_frontier_data_dictionary import default_cohort_foundation_frontier_data_dictionary
from glio_noncode.cohort_foundation_frontier_dataset_manifest import build_cohort_foundation_frontier_dataset_manifest
from glio_noncode.cohort_foundation_frontier_contracts import default_cohort_foundation_frontier_contracts
from glio_noncode.cohort_foundation_frontier_depth import audit_cohort_foundation_frontier_depth
from glio_noncode.cohort_foundation_frontier_diagnostics import CohortFoundationDiagnosticSeverity, build_cohort_foundation_frontier_diagnostics
from glio_noncode.cohort_foundation_frontier_exports import export_cohort_foundation_frontier_canonical, export_cohort_foundation_frontier_review_csv, export_cohort_foundation_frontier_review_markdown
from glio_noncode.cohort_foundation_frontier_fixture_eval import evaluate_cohort_foundation_frontier_fixture, execute_cohort_foundation_record
from glio_noncode.cohort_foundation_frontier_failure_injection import run_cohort_foundation_frontier_failure_injections
from glio_noncode.cohort_foundation_frontier_integrity import evaluate_cohort_foundation_frontier_integrity
from glio_noncode.cohort_foundation_frontier_lineage import CohortFoundationLineageNodeKind, build_cohort_foundation_frontier_lineage
from glio_noncode.cohort_foundation_frontier_metrics import measure_cohort_foundation_frontier
from glio_noncode.cohort_foundation_frontier_operational import build_cohort_foundation_frontier_operational_matrix
from glio_noncode.cohort_foundation_frontier_observability import observe_cohort_foundation_frontier
from glio_noncode.cohort_foundation_frontier_package import build_cohort_foundation_frontier_package_manifest
from glio_noncode.cohort_foundation_frontier_performance import build_cohort_foundation_frontier_performance_report
from glio_noncode.cohort_foundation_frontier_policy import CohortFoundationDisposition, materialize_cohort_foundation_frontier_policy
from glio_noncode.cohort_foundation_frontier_provenance import build_cohort_foundation_frontier_provenance
from glio_noncode.cohort_foundation_frontier_public_data import CohortFoundationOperation, CohortFoundationRole, audit_cohort_foundation_frontier_data, default_cohort_foundation_frontier_fixture
from glio_noncode.cohort_foundation_frontier_quality_gate import evaluate_cohort_foundation_frontier_quality
from glio_noncode.cohort_foundation_frontier_query import query_cohort_foundation_frontier
from glio_noncode.cohort_foundation_frontier_reconciliation import reconcile_cohort_foundation_frontier
from glio_noncode.cohort_foundation_frontier_release import CohortFoundationReleaseState, build_cohort_foundation_frontier_release_manifest
from glio_noncode.cohort_foundation_frontier_recovery import build_cohort_foundation_frontier_recovery_plan
from glio_noncode.cohort_foundation_frontier_review_sla import build_cohort_foundation_frontier_review_sla
from glio_noncode.cohort_foundation_frontier_retention import default_cohort_foundation_frontier_retention_report
from glio_noncode.cohort_foundation_frontier_reproducibility import build_cohort_foundation_frontier_reproducibility_receipt
from glio_noncode.cohort_foundation_frontier_replay import compare_cohort_foundation_frontier_replays, replay_cohort_foundation_frontier, replay_cohort_foundation_frontier_is_deterministic
from glio_noncode.cohort_foundation_frontier_report import build_cohort_foundation_frontier_report
from glio_noncode.cohort_foundation_frontier_runbook import build_cohort_foundation_frontier_runbook, cohort_foundation_frontier_runbook_is_executable
from glio_noncode.cohort_foundation_frontier_runtime import run_cohort_foundation_frontier_runtime
from glio_noncode.cohort_foundation_frontier_scenario_matrix import build_cohort_foundation_frontier_scenario_matrix
from glio_noncode.cohort_foundation_frontier_schema import default_cohort_foundation_frontier_schema, validate_cohort_foundation_frontier_schema
from glio_noncode.cohort_foundation_frontier_schema_migrations import build_cohort_foundation_frontier_schema_migration_report
from glio_noncode.cohort_foundation_frontier_summary import build_cohort_foundation_frontier_summary
from glio_noncode.cohort_foundation_frontier_source_registry import build_cohort_foundation_frontier_source_registry
from glio_noncode.cohort_foundation_frontier_thresholds import build_cohort_foundation_frontier_threshold_report, default_cohort_foundation_frontier_threshold_profiles
from glio_noncode.cohort_foundation_frontier_traces import build_cohort_foundation_frontier_trace_ledger
from glio_noncode.cohort_foundation_frontier_transcript import build_cohort_foundation_frontier_transcript
from glio_noncode.cohort_foundation_frontier_validation_matrix import build_cohort_foundation_frontier_validation_matrix
from glio_noncode.cohort_foundation_frontier_views import build_cohort_foundation_frontier_review_view


class CohortFoundationFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_cohort_foundation_frontier_fixture()
        cls.audit = audit_cohort_foundation_frontier_data(cls.fixture)
        cls.contracts = default_cohort_foundation_frontier_contracts()
        cls.schema = default_cohort_foundation_frontier_schema()
        cls.evaluation = evaluate_cohort_foundation_frontier_fixture(cls.fixture)
        cls.metrics = measure_cohort_foundation_frontier(cls.evaluation)
        cls.lineage = build_cohort_foundation_frontier_lineage(cls.fixture, cls.evaluation)
        cls.policy = materialize_cohort_foundation_frontier_policy(cls.evaluation, cls.contracts)
        cls.reconciliation = reconcile_cohort_foundation_frontier(cls.fixture, cls.evaluation, cls.policy)
        cls.quality = evaluate_cohort_foundation_frontier_quality(cls.fixture, cls.evaluation, cls.contracts, cls.schema, cls.lineage, cls.reconciliation)
        cls.runtime = run_cohort_foundation_frontier_runtime(cls.fixture, run_id="test-foundation-runtime")

    def test_public_fixture_has_source_and_control_closure(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual({item.operation for item in self.fixture.records}, set(CohortFoundationOperation))
        self.assertTrue(all(item.url.startswith("https://") for item in self.fixture.sources))
        self.assertTrue(all(item.aggregate_only for item in self.fixture.sources))

    def test_data_audit_exposes_all_check_ids(self) -> None:
        self.assertEqual({item.check_id for item in self.audit.checks}, {"fixture-version", "source-count", "record-count", "source-closure", "context-closure", "operation-coverage", "positive-coverage", "control-coverage", "https-receipts", "aggregate-boundary"})
        self.assertFalse(self.audit.failures)

    def test_adapter_registry_normalizes_and_rejects_foreign_rows(self) -> None:
        registry = default_cohort_foundation_frontier_adapters()
        adapter = registry.by_operation(CohortFoundationOperation.COHORT_QUERY)
        rows = list(self.fixture.records_for(CohortFoundationOperation.COHORT_QUERY)[0].payload["rows"])
        receipt = adapter.normalize(rows, context_key=self.fixture.context_key)
        self.assertEqual(receipt.accepted_count, 2)
        self.assertEqual(receipt.rejected_count, 0)
        foreign = dict(rows[0]) | {"context_key": self.fixture.foreign_context_key}
        rejected = adapter.normalize([foreign], context_key=self.fixture.context_key)
        self.assertEqual(rejected.accepted_count, 0)
        self.assertEqual(rejected.rejected_reasons, ("row_0:context_mismatch",))

    def test_contracts_and_schema_cover_four_operations(self) -> None:
        self.assertEqual({item.operation for item in self.contracts.contracts}, set(CohortFoundationOperation))
        self.assertTrue(validate_cohort_foundation_frontier_schema(self.schema))
        for operation in CohortFoundationOperation:
            self.assertTrue(self.contracts.by_operation(operation).required_fields)
            self.assertTrue(self.schema.by_operation(operation).context_required)

    def test_evaluation_matches_every_positive_and_control(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        expected = {item.record_id: item.expected_state for item in self.fixture.records}
        actual = {item.record_id: item.actual_state for item in self.evaluation.executions}
        self.assertEqual(actual, expected)
        for execution in self.evaluation.executions:
            if execution.role is CohortFoundationRole.POSITIVE:
                self.assertEqual(execution.issues, ())
        self.assertEqual(self.evaluation.execution_map()["C02-CTRL-002"].issues, ("zero_observation",))
        self.assertEqual(self.evaluation.execution_map()["C03-CTRL-003"].actual_state, "out_of_domain")

    def test_metrics_keep_operation_and_state_counts(self) -> None:
        self.assertEqual(self.metrics.execution_count, 16)
        self.assertEqual(self.metrics.accepted_count, 16)
        self.assertEqual(self.metrics.positive_count, 4)
        self.assertEqual(self.metrics.control_count, 12)
        for operation in CohortFoundationOperation:
            metric = self.metrics.by_operation(operation)
            self.assertEqual(metric.total, 4)
            self.assertEqual(metric.positive, 1)
            self.assertEqual(metric.controls, 3)
            self.assertEqual(metric.accepted, 4)
            self.assertEqual(metric.supported, 1)

    def test_lineage_and_provenance_are_closed(self) -> None:
        self.assertEqual(self.lineage.roots, (self.fixture.fixture_id,))
        self.assertGreaterEqual(len(self.lineage.nodes), 33)
        self.assertGreaterEqual(len(self.lineage.edges), 32)
        self.assertTrue(any(item.kind is CohortFoundationLineageNodeKind.SOURCE for item in self.lineage.nodes))
        provenance = build_cohort_foundation_frontier_provenance(self.fixture, self.evaluation)
        self.assertTrue(provenance.closed)
        self.assertEqual(len(provenance.receipts), 16)
        self.assertEqual(provenance.for_record("C01-POS-001").context_key, self.fixture.context_key)

    def test_policy_reconciliation_and_review_preserve_boundaries(self) -> None:
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.policy.decision_for("C01-POS-001").disposition, CohortFoundationDisposition.ALLOW_DESCRIPTIVE)
        self.assertEqual(self.policy.decision_for("C01-CTRL-002").disposition, CohortFoundationDisposition.QUARANTINE)
        self.assertEqual(self.policy.decision_for("C02-CTRL-002").disposition, CohortFoundationDisposition.REVIEW)
        review = self.runtime.review
        self.assertGreaterEqual(len(review.items), 12)
        self.assertTrue(any(item.disposition is CohortFoundationDisposition.QUARANTINE for item in review.items))

    def test_quality_gate_and_runtime_are_accepted(self) -> None:
        self.assertTrue(self.quality.accepted)
        self.assertFalse(self.quality.blocking_failures)
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 39)
        self.assertTrue(all(item.accepted for item in self.runtime.stages))
        self.assertEqual(self.runtime.release.state, CohortFoundationReleaseState.READY)

    def test_replay_is_deterministic(self) -> None:
        left = replay_cohort_foundation_frontier(self.fixture, replay_id="left")
        right = replay_cohort_foundation_frontier(self.fixture, replay_id="right")
        comparison = compare_cohort_foundation_frontier_replays(left, right)
        self.assertTrue(left.deterministic)
        self.assertTrue(comparison.accepted)
        self.assertEqual(comparison.changed_records, ())
        self.assertTrue(replay_cohort_foundation_frontier_is_deterministic(self.fixture))

    def test_artifacts_depth_and_diagnostics_are_explicit(self) -> None:
        self.assertTrue(self.runtime.artifacts.complete)
        self.assertEqual(len(self.runtime.artifacts.artifacts), len(CohortFoundationArtifactKind))
        self.assertEqual(len(self.runtime.artifacts.by_kind(CohortFoundationArtifactKind.RELEASE)), 1)
        self.assertTrue(self.runtime.depth.accepted)
        self.assertTrue(self.runtime.diagnostics.accepted)
        self.assertTrue(any(item.severity is CohortFoundationDiagnosticSeverity.REVIEW for item in self.runtime.diagnostics.findings))

    def test_assurance_requires_review_and_quarantine_counts(self) -> None:
        assurance = build_cohort_foundation_frontier_assurance(self.runtime.release, self.runtime.depth, self.runtime.replay, self.runtime.diagnostics, len(self.runtime.review.items), sum(item.disposition is CohortFoundationDisposition.QUARANTINE for item in self.runtime.policy.decisions))
        self.assertTrue(assurance.accepted)
        self.assertGreater(assurance.review_count, 0)
        self.assertGreater(assurance.quarantine_count, 0)

    def test_scenario_validation_operational_and_claim_planes(self) -> None:
        scenarios = build_cohort_foundation_frontier_scenario_matrix(self.evaluation)
        self.assertTrue(scenarios.accepted)
        self.assertGreaterEqual(len(scenarios.scenarios), 12)
        validation = build_cohort_foundation_frontier_validation_matrix(self.contracts, self.evaluation)
        self.assertTrue(validation.accepted)
        operational = build_cohort_foundation_frontier_operational_matrix(self.policy)
        self.assertTrue(operational.accepted)
        boundary = build_cohort_foundation_frontier_claim_boundary(self.contracts)
        self.assertTrue(boundary.accepted)
        self.assertIn("diagnosis", boundary.prohibited_claims)

    def test_runbook_query_and_report_are_usable(self) -> None:
        runbook = build_cohort_foundation_frontier_runbook(self.runtime)
        self.assertTrue(cohort_foundation_frontier_runbook_is_executable(runbook))
        result = query_cohort_foundation_frontier(self.runtime.review_view, state="out_of_domain", limit=2)
        self.assertEqual(result.total, 4)
        self.assertEqual(len(result.rows), 2)
        report = build_cohort_foundation_frontier_report(self.runtime)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.sections), 4)

    def test_exports_are_stable_and_reviewable(self) -> None:
        csv_text = export_cohort_foundation_frontier_review_csv(self.runtime.review)
        markdown = export_cohort_foundation_frontier_review_markdown(self.runtime.review)
        canonical = export_cohort_foundation_frontier_canonical(self.runtime.release)
        self.assertTrue(csv_text.startswith("review_id,record_id,operation"))
        self.assertIn("| Record | Operation |", markdown)
        self.assertIn('"release_id"', canonical)

    def test_invariants_cover_the_complete_control_plane(self) -> None:
        definitions = default_cohort_foundation_frontier_invariants()
        report = run_cohort_foundation_frontier_invariants(self.fixture, self.evaluation, self.policy, self.reconciliation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(definitions), 12)
        self.assertEqual(len(report.results), 12)
        self.assertEqual(cohort_foundation_frontier_observation_map(report), {item.invariant_id: True for item in report.results})
        self.assertFalse(report.failures)

    def test_integrity_report_rejects_no_duplicate_addresses(self) -> None:
        report = evaluate_cohort_foundation_frontier_integrity(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 8)
        self.assertFalse(report.failures)

    def test_control_coverage_exposes_all_state_classes(self) -> None:
        coverage = build_cohort_foundation_frontier_control_coverage(self.evaluation)
        self.assertTrue(coverage.accepted)
        self.assertEqual(coverage.state_classes, ("supported", "partial", "absent", "abstained", "out_of_domain"))
        self.assertEqual(coverage.row_for(CohortFoundationOperation.COHORT_QUERY).state_counts["partial"], 1)
        self.assertEqual(coverage.row_for(CohortFoundationOperation.BACKGROUND_RATE).state_counts["abstained"], 1)
        self.assertEqual(coverage.row_for(CohortFoundationOperation.SEQUENCE_CONTROL).state_counts["absent"], 1)
        self.assertEqual(coverage.row_for(CohortFoundationOperation.CHROMATIN_CONTROL).state_counts["out_of_domain"], 1)

    def test_traces_link_three_evidence_planes(self) -> None:
        ledger = build_cohort_foundation_frontier_trace_ledger(self.fixture, self.evaluation, self.policy)
        self.assertTrue(ledger.accepted)
        self.assertEqual(len(ledger.traces), 16)
        trace = ledger.trace_for("C01-POS-001")
        self.assertEqual(tuple(step.ordinal for step in trace.steps), (1, 2, 3))
        self.assertEqual(tuple(step.plane for step in trace.steps), ("source", "execution", "policy"))
        self.assertEqual(trace.final_state, "supported")
        self.assertEqual(trace.disposition, "allow_descriptive")

    def test_source_registry_closes_all_fixture_citations(self) -> None:
        registry = build_cohort_foundation_frontier_source_registry(self.fixture)
        self.assertTrue(registry.closed)
        self.assertEqual(len(registry.entries), 5)
        self.assertEqual(registry.by_id("source-gdc").permitted_use, "aggregate research use")
        self.assertTrue(registry.by_id("source-encode").url.startswith("https://"))

    def test_threshold_report_has_profiles_and_boundary_probes(self) -> None:
        profiles = default_cohort_foundation_frontier_threshold_profiles()
        report = build_cohort_foundation_frontier_threshold_report()
        self.assertEqual(len(profiles), 4)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.profiles), 4)
        self.assertEqual(len(report.probes), 12)
        self.assertEqual({item.parameter for item in report.probes}, {"maximum_distance"})

    def test_observability_is_deterministic_when_timestamp_is_pinned(self) -> None:
        first = observe_cohort_foundation_frontier(self.fixture.fixture_id, self.runtime.stages, emitted_at="2026-08-22T00:00:00+00:00")
        second = observe_cohort_foundation_frontier(self.fixture.fixture_id, self.runtime.stages, emitted_at="2026-08-22T00:00:00+00:00")
        self.assertTrue(first.accepted)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(len(first.events), len(self.runtime.stages))
        self.assertEqual(first.failed_events, ())

    def test_failure_injections_prove_blocking_boundaries(self) -> None:
        report = run_cohort_foundation_frontier_failure_injections(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.results), 4)
        self.assertTrue(all(item.expected_blocked for item in report.results))
        self.assertTrue(all(item.accepted for item in report.results))
        self.assertIn("expected-state-drift", {item.mutation_id for item in report.results})

    def test_recovery_plan_retains_review_and_quarantine_paths(self) -> None:
        plan = build_cohort_foundation_frontier_recovery_plan(self.runtime.policy, self.runtime.quality, self.runtime.release)
        self.assertTrue(plan.executable)
        self.assertEqual(len(plan.steps), 5)
        self.assertGreater(plan.review_count, 0)
        self.assertGreater(plan.quarantine_count, 0)
        self.assertEqual(tuple(item.ordinal for item in plan.steps), tuple(range(1, 6)))

    def test_performance_report_is_bounded_for_each_operation(self) -> None:
        report = build_cohort_foundation_frontier_performance_report(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.total_records, 16)
        self.assertEqual({item.operation for item in report.budgets}, set(CohortFoundationOperation))
        self.assertTrue(all(item.within_fixture for item in report.budgets))
        self.assertIn("candidate-sort", {item.expected_complexity for item in report.budgets})

    def test_schema_migration_report_preserves_incompatible_boundary(self) -> None:
        report = build_cohort_foundation_frontier_schema_migration_report()
        self.assertTrue(report.accepted)
        self.assertEqual(report.current_version, "2.0.0")
        self.assertEqual(len(report.migrations), 3)
        self.assertFalse(report.migrations[-1].backward_compatible)
        self.assertIn("trace_steps", report.migrations[-1].added_fields)

    def test_accessibility_and_package_manifests_are_complete(self) -> None:
        accessibility = build_cohort_foundation_frontier_accessibility_report(self.runtime.review_view)
        self.assertTrue(accessibility.accepted)
        self.assertEqual(len(accessibility.fields), 7)
        self.assertEqual(accessibility.keyboard_order[0], "record_id")
        package = build_cohort_foundation_frontier_package_manifest(self.runtime.artifacts, self.runtime.release)
        self.assertTrue(package.ready)
        self.assertEqual(len(package.files), len(self.runtime.artifacts.artifacts))
        self.assertTrue(all(item.path.startswith("artifacts/") for item in package.files))

    def test_claim_evidence_links_are_context_bound(self) -> None:
        ledger = build_cohort_foundation_frontier_claim_evidence_ledger(self.evaluation, self.policy, self.fixture.context_key)
        self.assertTrue(ledger.accepted)
        self.assertEqual(len(ledger.links), 16)
        self.assertTrue(all(item.evidence_addresses for item in ledger.links))
        self.assertTrue(all(item.context_key == self.fixture.context_key for item in ledger.links))
        self.assertTrue(any(not item.allowed for item in ledger.links))

    def test_audit_log_is_append_only_and_ordered(self) -> None:
        addresses = [item.output_address for item in self.runtime.stages]
        log = build_cohort_foundation_frontier_audit_log(self.fixture.fixture_id, addresses)
        self.assertTrue(log.append_only)
        self.assertEqual(len(log.entries), len(addresses))
        self.assertEqual(tuple(item.ordinal for item in log.entries), tuple(range(1, len(addresses) + 1)))
        self.assertEqual(log.entries[0].previous_address, "")
        self.assertEqual(log.entries[1].previous_address, addresses[0])

    def test_review_sla_prioritizes_quarantine_items(self) -> None:
        report = build_cohort_foundation_frontier_review_sla(self.runtime.review)
        self.assertTrue(report.accepted)
        self.assertGreater(len(report.items), 0)
        self.assertTrue(all(item.target_hours > 0 for item in report.items))
        self.assertIn("urgent", {item.priority for item in report.items})

    def test_data_dictionary_and_compatibility_are_explicit(self) -> None:
        dictionary = default_cohort_foundation_frontier_data_dictionary()
        self.assertTrue(dictionary.accepted)
        self.assertEqual(len(dictionary.entries), 8)
        self.assertEqual(dictionary.by_field("callable_bases").unit, "bases")
        self.assertEqual(dictionary.by_field("background_rate").nullable, True)
        compatibility = evaluate_cohort_foundation_frontier_compatibility(self.runtime.release)
        self.assertTrue(compatibility.accepted)
        self.assertEqual(len(compatibility.checks), 4)

    def test_change_control_requires_replay_and_quality_for_each_change_class(self) -> None:
        report = default_cohort_foundation_frontier_change_control_report()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.items), 5)
        self.assertEqual({item.change_class for item in report.items}, {"source", "schema", "threshold", "policy", "release"})
        self.assertTrue(all(item.required_replay and item.required_quality_gate for item in report.items))

    def test_retention_report_separates_immutable_and_expiring_artifacts(self) -> None:
        report = default_cohort_foundation_frontier_retention_report()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.rules), 5)
        self.assertTrue(any(item.retention_days is None for item in report.rules))
        self.assertTrue(any(item.deletion_allowed for item in report.rules))

    def test_reproducibility_receipt_captures_every_runtime_stage(self) -> None:
        receipt = build_cohort_foundation_frontier_reproducibility_receipt(self.fixture.fixture_version, self.fixture.to_dict()["content_address"], self.runtime.stages)
        self.assertTrue(receipt.deterministic)
        self.assertEqual(len(receipt.stage_addresses), len(self.runtime.stages))
        self.assertEqual(len(receipt.commands), len(self.runtime.stages))
        self.assertEqual(receipt.pinned_timestamp, "2026-08-22T00:00:00+00:00")

    def test_dataset_manifest_closes_counts_and_sources(self) -> None:
        manifest = build_cohort_foundation_frontier_dataset_manifest(self.fixture)
        self.assertEqual(manifest.record_count, 16)
        self.assertEqual(manifest.positive_count, 4)
        self.assertEqual(manifest.control_count, 12)
        self.assertEqual(set(manifest.operation_counts.values()), {4})
        self.assertEqual(len(manifest.source_ids), 5)

    def test_transcript_is_ordered_and_renderable(self) -> None:
        transcript = build_cohort_foundation_frontier_transcript(self.runtime.stages)
        self.assertTrue(transcript.accepted)
        self.assertEqual(len(transcript.lines), len(self.runtime.stages))
        self.assertIn("01 ACCEPTED", transcript.to_text())
        self.assertEqual(transcript.lines[-1].ordinal, len(self.runtime.stages))

    def test_summary_matches_runtime_counts(self) -> None:
        summary = build_cohort_foundation_frontier_summary(self.runtime)
        self.assertTrue(summary.accepted)
        self.assertEqual(summary.record_count, 16)
        self.assertEqual(summary.positive_count, 4)
        self.assertEqual(summary.control_count, 12)
        self.assertEqual(summary.stage_count, 39)


if __name__ == "__main__":
    unittest.main()
