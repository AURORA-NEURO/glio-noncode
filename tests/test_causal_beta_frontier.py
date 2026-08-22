from __future__ import annotations

import json
import unittest

from glio_noncode.causal_beta import CausalBetaState
from glio_noncode.causal_beta_frontier_adapters import build_causal_beta_frontier_adapters, execute_causal_beta_frontier_record
from glio_noncode.causal_beta_frontier_artifacts import build_causal_beta_frontier_artifact_inventory
from glio_noncode.causal_beta_frontier_assurance import build_causal_beta_frontier_assurance
from glio_noncode.causal_beta_frontier_bundle import CausalBetaFrontierBundleState, assemble_causal_beta_frontier_bundle
from glio_noncode.causal_beta_frontier_claim_boundary import build_causal_beta_frontier_claim_boundary
from glio_noncode.causal_beta_frontier_contracts import build_causal_beta_frontier_contracts
from glio_noncode.causal_beta_frontier_depth import audit_causal_beta_frontier_depth
from glio_noncode.causal_beta_frontier_exports import build_causal_beta_frontier_exports, export_causal_beta_frontier_json, export_causal_beta_frontier_review_csv, export_causal_beta_frontier_review_markdown
from glio_noncode.causal_beta_frontier_fixture_eval import evaluate_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_integrity import evaluate_causal_beta_frontier_integrity
from glio_noncode.causal_beta_frontier_lineage import build_causal_beta_frontier_lineage, verify_causal_beta_frontier_lineage
from glio_noncode.causal_beta_frontier_metrics import build_causal_beta_frontier_metrics
from glio_noncode.causal_beta_frontier_operational import build_causal_beta_frontier_operational_matrix
from glio_noncode.causal_beta_frontier_policy import CausalBetaFrontierDecision, default_causal_beta_frontier_policy
from glio_noncode.causal_beta_frontier_provenance import build_causal_beta_frontier_provenance
from glio_noncode.causal_beta_frontier_public_data import CAUSAL_BETA_FRONTIER_CONTEXT_KEY, CAUSAL_BETA_FRONTIER_FOREIGN_CONTEXT_KEY, CausalBetaFrontierOperation, CausalBetaFrontierRole, audit_causal_beta_frontier_data, causal_beta_frontier_fixture_json, default_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_query import CausalBetaFrontierQuery, build_causal_beta_frontier_query_index, query_causal_beta_frontier
from glio_noncode.causal_beta_frontier_reconciliation import reconcile_causal_beta_frontier
from glio_noncode.causal_beta_frontier_release import CausalBetaFrontierReleaseState, build_causal_beta_frontier_release_manifest
from glio_noncode.causal_beta_frontier_replay import compare_causal_beta_frontier_replays, replay_causal_beta_frontier, replay_is_deterministic
from glio_noncode.causal_beta_frontier_report import build_causal_beta_frontier_report
from glio_noncode.causal_beta_frontier_review import build_causal_beta_frontier_review_queue
from glio_noncode.causal_beta_frontier_scenario_matrix import build_causal_beta_frontier_scenario_matrix
from glio_noncode.causal_beta_frontier_schema import validate_causal_beta_frontier_schema
from glio_noncode.causal_beta_frontier_validation_matrix import build_causal_beta_frontier_validation_matrix
from glio_noncode.causal_beta_frontier_views import build_causal_beta_frontier_review_view, build_causal_beta_frontier_summary_view
from glio_noncode.causal_beta_frontier_quality_gate import evaluate_causal_beta_frontier_quality
from glio_noncode.causal_beta_frontier_runtime import run_causal_beta_frontier_runtime
from glio_noncode.errors import ValidationError


class CausalBetaFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_causal_beta_frontier_fixture()
        cls.audit = audit_causal_beta_frontier_data(cls.fixture)
        cls.adapters = build_causal_beta_frontier_adapters()
        cls.evaluation = evaluate_causal_beta_frontier_fixture(cls.fixture)
        cls.contracts = build_causal_beta_frontier_contracts()
        cls.schema = validate_causal_beta_frontier_schema(cls.fixture, cls.evaluation)
        cls.metrics = build_causal_beta_frontier_metrics(cls.evaluation, cls.fixture)
        cls.lineage = build_causal_beta_frontier_lineage(cls.fixture, cls.evaluation)
        cls.provenance = build_causal_beta_frontier_provenance(cls.fixture, cls.evaluation)
        cls.depth = audit_causal_beta_frontier_depth(cls.fixture, cls.evaluation, cls.adapters, cls.contracts, cls.schema, cls.metrics, cls.lineage, cls.provenance)
        cls.policy = default_causal_beta_frontier_policy()
        cls.decisions = cls.policy.decide(cls.evaluation)
        cls.reconciliation = reconcile_causal_beta_frontier(cls.fixture, cls.evaluation, cls.decisions, cls.policy)
        cls.review = build_causal_beta_frontier_review_queue(cls.evaluation, cls.policy)
        cls.scenario = build_causal_beta_frontier_scenario_matrix(cls.fixture, cls.evaluation)
        cls.validation = build_causal_beta_frontier_validation_matrix(cls.fixture, cls.evaluation)
        cls.gate = evaluate_causal_beta_frontier_quality(cls.fixture, cls.evaluation, cls.contracts, cls.schema, cls.metrics, cls.lineage, cls.reconciliation, cls.depth, cls.review, cls.decisions)
        cls.bundle = assemble_causal_beta_frontier_bundle(cls.fixture, cls.evaluation, cls.metrics, cls.contracts, cls.schema, cls.lineage, cls.provenance, cls.depth, cls.reconciliation, cls.policy, cls.review, cls.gate, cls.scenario, cls.validation)
        cls.release = build_causal_beta_frontier_release_manifest(cls.bundle, cls.gate, cls.depth, cls.review)
        cls.artifacts = build_causal_beta_frontier_artifact_inventory(cls.fixture, cls.evaluation, cls.bundle, cls.release)
        cls.replay = replay_causal_beta_frontier(cls.fixture)
        cls.operational = build_causal_beta_frontier_operational_matrix(cls.fixture, cls.evaluation, cls.decisions, cls.review, cls.bundle)
        cls.boundary = build_causal_beta_frontier_claim_boundary(cls.bundle, cls.operational)
        cls.review_view = build_causal_beta_frontier_review_view(cls.fixture, cls.evaluation, cls.decisions, cls.reconciliation, cls.review)
        cls.exports = build_causal_beta_frontier_exports(cls.fixture, cls.evaluation, cls.metrics, cls.review_view, cls.bundle, cls.release, cls.artifacts)
        cls.integrity = evaluate_causal_beta_frontier_integrity(cls.fixture, cls.evaluation, cls.lineage, cls.provenance)
        cls.runtime = run_causal_beta_frontier_runtime(cls.fixture, run_id="test-causal-beta-frontier")
        cls.assurance = build_causal_beta_frontier_assurance(cls.runtime, cls.replay, cls.integrity, cls.operational, cls.boundary, cls.exports, cls.release)

    def test_fixture_is_closed_over_four_operations(self) -> None:
        self.assertEqual(self.audit.record_count, 16)
        self.assertEqual(self.audit.source_count, 5)
        self.assertEqual(self.audit.positive_count, 4)
        self.assertEqual(self.audit.control_count, 12)
        self.assertEqual(self.audit.foreign_context_count, 4)
        self.assertTrue(self.audit.accepted)
        self.assertEqual(set(item.operation for item in self.fixture.records), set(CausalBetaFrontierOperation))
        self.assertEqual(set(item.role for item in self.fixture.records), {CausalBetaFrontierRole.POSITIVE, CausalBetaFrontierRole.CONTROL})
        self.assertTrue(all(item.context_key in {CAUSAL_BETA_FRONTIER_CONTEXT_KEY, CAUSAL_BETA_FRONTIER_FOREIGN_CONTEXT_KEY} for item in self.fixture.records))

    def test_fixture_records_have_resolved_sources_payloads_and_receipts(self) -> None:
        source_ids = set(self.fixture.source_map())
        self.assertEqual(len(self.fixture.record_map()), len(self.fixture.records))
        for record in self.fixture.records:
            self.assertTrue(set(record.source_ids) <= source_ids)
            self.assertTrue(record.payload)
            self.assertTrue(record.description)
            self.assertTrue(record.content_address.startswith("sha256:"))
            self.assertTrue(record.expected_state in set(CausalBetaState))
        for source in self.fixture.sources:
            self.assertTrue(source.uri.startswith("https://"))
            self.assertTrue(source.content_address.startswith("sha256:"))

    def test_fixture_json_is_deterministic_and_serializable(self) -> None:
        first = causal_beta_frontier_fixture_json(self.fixture)
        second = causal_beta_frontier_fixture_json(default_causal_beta_frontier_fixture())
        self.assertEqual(first, second)
        decoded = json.loads(first)
        self.assertEqual(decoded["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(len(decoded["records"]), 16)
        self.assertEqual(len(decoded["sources"]), 5)

    def test_adapter_registry_has_one_spec_per_operation(self) -> None:
        self.assertTrue(self.adapters.accepted)
        self.assertEqual(len(self.adapters.specs), 4)
        self.assertEqual({item.operation for item in self.adapters.specs}, set(CausalBetaFrontierOperation))
        for operation in CausalBetaFrontierOperation:
            spec = self.adapters.for_operation(operation)
            self.assertTrue(spec.adapter_id)
            self.assertTrue(spec.primitive)
            self.assertIn("context_key", spec.input_fields)
            self.assertIn("state", spec.output_fields)
            self.assertIn("not", spec.limitation)

    def test_adapter_results_preserve_row_identity_and_source_receipts(self) -> None:
        for record in self.fixture.records:
            result = execute_causal_beta_frontier_record(record)
            self.assertEqual(result.record_id, record.record_id)
            self.assertEqual(result.operation, record.operation)
            self.assertEqual(result.state, record.expected_state)
            self.assertEqual(result.issue_codes, tuple(record.expected_issue_codes))
            self.assertTrue(result.content_address.startswith("sha256:"))
            if record.role is CausalBetaFrontierRole.POSITIVE:
                self.assertTrue(result.source_ids or result.evidence_ids)

    def test_evaluation_replays_every_positive_and_control(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.rows), 16)
        self.assertEqual(self.evaluation.state_match_count, 16)
        self.assertEqual(self.evaluation.issue_match_count, 16)
        self.assertEqual(self.evaluation.failed_record_ids, ())
        self.assertEqual(self.evaluation.state_counts, {"ambiguous": 1, "contradictory": 3, "out_of_domain": 4, "partial": 4, "supported": 4})
        self.assertEqual(self.evaluation.issue_counts, {"context_mismatch": 4, "contradictory_direction": 2, "minimum_independent_sources": 3, "missing_alternate_allele": 1, "negative_control_conflict": 1, "replicate_ambiguity": 1})

    def test_evaluation_supports_operation_and_state_slices(self) -> None:
        for operation in CausalBetaFrontierOperation:
            rows = self.evaluation.by_operation(operation.value)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role == "positive" for item in rows), 1)
            self.assertEqual(sum(item.role == "control" for item in rows), 3)
            self.assertEqual(len(self.fixture.operation_records(operation)), 4)
        self.assertEqual(len(self.evaluation.by_state("supported")), 4)
        self.assertEqual(len(self.evaluation.by_state("partial")), 4)
        self.assertEqual(len(self.evaluation.by_state("contradictory")), 3)
        self.assertEqual(len(self.evaluation.by_state("ambiguous")), 1)
        self.assertEqual(len(self.evaluation.by_state("out_of_domain")), 4)

    def test_metrics_report_exact_counts_and_per_operation_accuracy(self) -> None:
        self.assertTrue(self.metrics.accepted)
        self.assertEqual(self.metrics.record_count, 16)
        self.assertEqual(self.metrics.positive_count, 4)
        self.assertEqual(self.metrics.control_count, 12)
        self.assertEqual(self.metrics.state_accuracy, 1.0)
        self.assertEqual(self.metrics.issue_accuracy, 1.0)
        for operation in CausalBetaFrontierOperation:
            metric = self.metrics.for_operation(operation.value)
            self.assertEqual(metric.record_count, 4)
            self.assertEqual(metric.positive_count, 1)
            self.assertEqual(metric.control_count, 3)
            self.assertEqual(metric.state_matches, 4)
            self.assertEqual(metric.issue_matches, 4)
            self.assertTrue(metric.accepted)

    def test_contract_report_covers_all_four_capabilities(self) -> None:
        self.assertTrue(self.contracts.accepted)
        self.assertEqual(len(self.contracts.contracts), 4)
        self.assertEqual({item.capability_id for item in self.contracts.contracts}, {"GNC-D11-C05", "GNC-D11-C06", "GNC-D11-C07", "GNC-D11-C08"})
        for contract in self.contracts.contracts:
            self.assertEqual(len(contract.required_fields), len(set(contract.required_fields)))
            self.assertTrue(contract.required_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.limitation)
            self.assertTrue(contract.content_address.startswith("sha256:"))

    def test_schema_report_validates_record_envelope(self) -> None:
        self.assertTrue(self.schema.accepted)
        self.assertEqual(len(self.schema.fields), 10)
        self.assertEqual(self.schema.failed_checks, ())
        self.assertEqual(sum(item.required for item in self.schema.fields), 9)
        self.assertEqual({item.name for item in self.schema.fields}, {"record_id", "operation", "role", "context_key", "source_ids", "payload", "expected_state", "expected_issue_codes", "description", "content_address"})

    def test_depth_audit_requires_multiple_independent_planes(self) -> None:
        self.assertTrue(self.depth.accepted)
        self.assertEqual(len(self.depth.checks), 10)
        self.assertEqual(self.depth.failed_check_ids, ())
        self.assertTrue(all(item.observed for item in self.depth.checks))
        check_ids = {item.check_id for item in self.depth.checks}
        self.assertIn("adapter-closure", check_ids)
        self.assertIn("source-density", check_ids)
        self.assertIn("control-density", check_ids)
        self.assertIn("context-boundary", check_ids)

    def test_lineage_has_fixture_source_and_result_edges(self) -> None:
        self.assertTrue(self.lineage.accepted)
        self.assertTrue(verify_causal_beta_frontier_lineage(self.lineage, self.fixture))
        self.assertEqual(len(self.lineage.fixture_edges), 16)
        self.assertEqual(len(self.lineage.record_edges), 16)
        self.assertGreaterEqual(len(self.lineage.source_edges), 16)
        self.assertEqual(len({item.content_address for item in self.lineage.edges}), len(self.lineage.edges))
        for record in self.fixture.records:
            self.assertEqual(len(self.lineage.for_record(record.record_id)), 2 + len(record.source_ids))

    def test_provenance_graph_has_no_orphans(self) -> None:
        self.assertTrue(self.provenance.accepted)
        self.assertEqual(self.provenance.orphan_node_ids, ())
        self.assertEqual(len(self.provenance.edges), len(self.lineage.edges))
        self.assertGreater(len(self.provenance.nodes), 16)
        self.assertTrue(all(item.node_id for item in self.provenance.nodes))
        self.assertTrue(all(item.parent_id in self.provenance.node_ids and item.child_id in self.provenance.node_ids for item in self.provenance.edges))

    def test_integrity_report_verifies_receipts_and_graph_alignment(self) -> None:
        self.assertTrue(self.integrity.accepted)
        self.assertEqual(self.integrity.failed_check_ids, ())
        self.assertEqual(len(self.integrity.checks), 9)
        self.assertTrue(all(item.passed for item in self.integrity.checks))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.integrity.checks))

    def test_policy_produces_explicit_disposition_for_every_row(self) -> None:
        self.assertEqual(len(self.decisions), 16)
        self.assertEqual(sum(item.decision is CausalBetaFrontierDecision.RETAIN for item in self.decisions), 4)
        self.assertEqual(sum(item.decision is CausalBetaFrontierDecision.REVIEW for item in self.decisions), 4)
        self.assertEqual(sum(item.decision is CausalBetaFrontierDecision.ABSTAIN for item in self.decisions), 1)
        self.assertEqual(sum(item.decision is CausalBetaFrontierDecision.QUARANTINE for item in self.decisions), 7)
        for decision in self.decisions:
            self.assertTrue(decision.record_id)
            self.assertTrue(decision.reason)
            self.assertTrue(decision.content_address.startswith("sha256:"))

    def test_reconciliation_keeps_expected_state_and_issue_floor(self) -> None:
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.reconciliation.accepted_count, 9)
        self.assertEqual(self.reconciliation.mismatch_record_ids, ())
        self.assertEqual(len(self.reconciliation.items), 16)
        self.assertEqual(sum(item.accepted for item in self.reconciliation.items), 9)
        self.assertTrue(all(item.state_match and item.issue_match for item in self.reconciliation.items))

    def test_review_queue_exposes_retained_review_and_blocked_rows(self) -> None:
        self.assertTrue(self.review.accepted)
        self.assertEqual(len(self.review.items), 16)
        self.assertEqual(self.review.retained_count, 4)
        self.assertEqual(self.review.review_count, 5)
        self.assertEqual(self.review.blocked_count, 8)
        self.assertEqual(len(self.review.blocking_record_ids), 8)
        self.assertEqual(len(self.review.for_priority("critical")), 7)
        self.assertEqual(len(self.review.for_priority("high")), 1)
        self.assertEqual(len(self.review.for_priority("normal")), 4)
        self.assertEqual(len(self.review.for_priority("informational")), 4)
        for item in self.review.items:
            self.assertTrue(item.required_checks)
            self.assertTrue(item.rationale)

    def test_scenario_and_validation_matrices_cover_four_operations(self) -> None:
        self.assertTrue(self.scenario.accepted)
        self.assertTrue(self.validation.accepted)
        self.assertEqual(len(self.scenario.scenarios), 16)
        self.assertEqual(len(self.validation.cells), 16)
        self.assertEqual({item.operation for item in self.scenario.scenarios}, {item.value for item in CausalBetaFrontierOperation})
        self.assertEqual({item.operation for item in self.validation.cells}, {item.value for item in CausalBetaFrontierOperation})
        for operation in CausalBetaFrontierOperation:
            self.assertEqual(len(self.scenario.for_operation(operation.value)), 4)
            self.assertEqual(len(tuple(item for item in self.validation.cells if item.operation == operation.value)), 4)

    def test_quality_gate_has_no_failed_checks(self) -> None:
        self.assertTrue(self.gate.accepted)
        self.assertEqual(self.gate.failed_count, 0)
        self.assertEqual(self.gate.blocking_check_ids, ())
        self.assertGreaterEqual(len(self.gate.checks), 13)
        self.assertTrue(all(item.passed for item in self.gate.checks))

    def test_bundle_and_release_manifest_are_ready(self) -> None:
        self.assertTrue(self.bundle.publishable)
        self.assertEqual(self.bundle.state, CausalBetaFrontierBundleState.READY)
        self.assertTrue(self.release.accepted)
        self.assertEqual(self.release.state, CausalBetaFrontierReleaseState.READY)
        self.assertEqual(self.release.failed_check_ids, ())
        self.assertEqual(self.release.passed_count, 5)
        self.assertIn("patient care", self.release.excluded_uses)
        self.assertIn("aggregate evidence review", self.release.allowed_uses)

    def test_artifact_inventory_is_complete(self) -> None:
        self.assertTrue(self.artifacts.accepted)
        self.assertEqual(len(self.artifacts.artifacts), 16)
        self.assertEqual(self.artifacts.missing_artifact_ids, ())
        self.assertEqual(len(set(item.artifact_id for item in self.artifacts.artifacts)), 16)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.artifacts.artifacts))

    def test_replay_receipt_is_deterministic(self) -> None:
        self.assertTrue(self.replay.accepted)
        self.assertTrue(self.replay.deterministic)
        self.assertEqual(self.replay.first_address, self.replay.second_address)
        self.assertEqual(self.replay.row_count, 16)
        self.assertTrue(replay_is_deterministic(self.fixture))
        left = evaluate_causal_beta_frontier_fixture(self.fixture)
        right = evaluate_causal_beta_frontier_fixture(default_causal_beta_frontier_fixture())
        comparison = compare_causal_beta_frontier_replays(left, right)
        self.assertTrue(comparison.accepted)
        self.assertTrue(comparison.identical)
        self.assertEqual(comparison.changed_record_ids, ())

    def test_operational_matrix_has_four_allowed_positive_cells(self) -> None:
        self.assertTrue(self.operational.accepted)
        self.assertEqual(len(self.operational.cells), 16)
        self.assertEqual(self.operational.allowed_count, 4)
        self.assertEqual(self.operational.review_count, 5)
        self.assertEqual(self.operational.blocked_count, 7)
        self.assertEqual(len(self.operational.for_scenario("positive")), 4)
        self.assertEqual(len(self.operational.for_scenario("foreign_context")), 4)
        for cell in self.operational.for_scenario("positive"):
            self.assertEqual(cell.action, "retain_for_bounded_analysis")
            self.assertTrue(cell.release_allowed)
            self.assertFalse(cell.review_required)

    def test_claim_boundary_makes_allowed_and_excluded_uses_machine_visible(self) -> None:
        self.assertTrue(self.boundary.accepted)
        self.assertEqual(len(self.boundary.allowed), 3)
        self.assertEqual(len(self.boundary.excluded), 4)
        self.assertEqual(len(self.boundary.all_boundaries), 7)
        self.assertTrue(all(item.enforced for item in self.boundary.all_boundaries))
        statements = {item.statement for item in self.boundary.excluded}
        self.assertTrue(any("patient" in item for item in statements))
        self.assertTrue(any("diagnosis" in item for item in statements))

    def test_review_view_and_exports_are_stable(self) -> None:
        self.assertEqual(len(self.review_view.rows), 16)
        self.assertEqual(len(self.review_view.columns), 12)
        self.assertEqual(len(self.review_view.by_operation("sequence_to_element")), 4)
        csv_text = export_causal_beta_frontier_review_csv(self.review_view)
        markdown = export_causal_beta_frontier_review_markdown(self.review_view)
        self.assertTrue(csv_text.startswith("record_id,operation"))
        self.assertIn("D11-C05-P", csv_text)
        self.assertNotIn("#", markdown)
        self.assertIn("| record_id |", markdown)
        self.assertTrue(self.exports.accepted)
        self.assertEqual(len(self.exports.envelopes), 6)
        self.assertEqual(set(self.exports.export_kinds), {"fixture-json", "evaluation-json", "summary-json", "review-csv", "review-markdown", "release-manifest-json"})
        decoded = json.loads(export_causal_beta_frontier_json(self.exports))
        self.assertEqual(decoded["export_count"], 6)

    def test_summary_view_and_report_are_human_queryable(self) -> None:
        summary = build_causal_beta_frontier_summary_view(self.fixture, self.metrics, self.review, True)
        self.assertTrue(summary.accepted)
        self.assertEqual(summary.retained_count, 4)
        self.assertEqual(summary.review_count, 5)
        self.assertEqual(summary.blocked_count, 8)
        self.assertEqual(summary.top_issue_codes[0], ("context_mismatch", 4))
        report = build_causal_beta_frontier_report(self.fixture, self.metrics, self.review, self.operational, self.assurance)
        self.assertTrue(report.accepted)
        markdown = report.to_markdown()
        self.assertIn("C05-C08", markdown)
        self.assertIn("Observed states", markdown)
        self.assertIn("Boundary", markdown)

    def test_query_index_and_filters_are_composable(self) -> None:
        index = build_causal_beta_frontier_query_index(self.fixture, self.evaluation)
        self.assertEqual(len(index.record_ids), 16)
        self.assertEqual(len(index.operations), 4)
        self.assertIn("supported", index.states)
        self.assertIn("context_mismatch", index.issue_codes)
        positive = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(role="positive"), self.review)
        self.assertEqual(positive.record_ids, ("D11-C05-P", "D11-C06-P", "D11-C07-P", "D11-C08-P"))
        supported = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(state="supported"), self.review)
        self.assertEqual(len(supported.rows), 4)
        foreign = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(issue_code="context_mismatch"), self.review)
        self.assertEqual(len(foreign.rows), 4)
        retained = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(accepted_only=True), self.review)
        self.assertEqual(len(retained.rows), 8)
        one = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(record_id="D11-C08-C2"), self.review)
        self.assertEqual(one.record_ids, ("D11-C08-C2",))

    def test_runtime_report_is_ordered_and_accepted(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.stage_count, 27)
        self.assertEqual(self.runtime.stage_ids[0], "data-audit")
        self.assertEqual(self.runtime.stage_ids[-1], "runbook")
        self.assertEqual(tuple(item.sequence for item in self.runtime.stages), tuple(range(1, 28)))
        self.assertTrue(all(item.state == "completed" for item in self.runtime.stages))
        self.assertTrue(self.runtime.observability.accepted)
        self.assertEqual(len(self.runtime.observability.events), 27)
        self.assertEqual(self.runtime.assurance.assurance_id, "causal-beta-frontier-assurance")

    def test_assurance_statement_requires_every_release_plane(self) -> None:
        self.assertTrue(self.assurance.accepted)
        self.assertTrue(self.assurance.runtime_accepted)
        self.assertTrue(self.assurance.replay_deterministic)
        self.assertTrue(self.assurance.integrity_accepted)
        self.assertTrue(self.assurance.operational_accepted)
        self.assertTrue(self.assurance.boundary_accepted)
        self.assertTrue(self.assurance.exports_accepted)
        self.assertIn("bounded", self.assurance.headline)
        self.assertTrue(self.assurance.limitations)

    def test_public_source_and_record_dataclasses_reject_invalid_envelopes(self) -> None:
        source = self.fixture.sources[0]
        with self.assertRaises(ValidationError):
            type(source)(source.source_id, source.title, "http://not-https.example", source.source_kind, source.release, source.scope)
        record = self.fixture.records[0]
        with self.assertRaises(ValidationError):
            type(record)(record.record_id, "not-an-operation", record.role, record.context_key, record.source_ids, record.payload, record.expected_state, record.expected_issue_codes, record.description)

    def test_content_addresses_exist_across_all_release_planes(self) -> None:
        values = (self.fixture, self.evaluation, self.contracts, self.schema, self.metrics, self.lineage, self.provenance, self.depth, self.reconciliation, self.review, self.scenario, self.validation, self.gate, self.bundle, self.release, self.artifacts, self.replay, self.operational, self.boundary, self.review_view, self.exports, self.integrity, self.runtime, self.assurance)
        for value in values:
            self.assertTrue(getattr(value, "content_address").startswith("sha256:"), type(value).__name__)


if __name__ == "__main__":
    unittest.main()
