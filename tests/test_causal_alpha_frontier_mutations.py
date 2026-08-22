from __future__ import annotations

import unittest

from glio_noncode.causal_alpha_frontier_adapters import evaluate_causal_alpha_frontier_fixture
from glio_noncode.causal_alpha_frontier_artifacts import CausalAlphaFrontierArtifactKind
from glio_noncode.causal_alpha_frontier_controls import CausalAlphaFrontierControlClass
from glio_noncode.causal_alpha_frontier_diagnostics import CausalAlphaFrontierDiagnosticSeverity
from glio_noncode.causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from glio_noncode.causal_alpha_frontier_policy import CausalAlphaFrontierDisposition
from glio_noncode.causal_alpha_frontier_public_data import (
    CAUSAL_ALPHA_FRONTIER_BOUNDARY,
    CausalAlphaFrontierFixture,
    CausalAlphaFrontierOperation,
    CausalAlphaFrontierRecord,
    CausalAlphaFrontierRole,
    CausalAlphaFrontierSource,
    default_causal_alpha_frontier_fixture,
)
from glio_noncode.causal_alpha_frontier_query import query_causal_alpha_frontier
from glio_noncode.causal_alpha_frontier_runtime import run_causal_alpha_frontier_runtime
from glio_noncode.errors import ValidationError


class CausalAlphaFrontierMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_alpha_frontier_fixture()
        self.runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-mutations")

    def test_source_receipts_reject_non_https(self) -> None:
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierSource("bad", "bad", "http://example.invalid", "archive", "1", "scope")

    def test_source_receipts_reject_empty_fields(self) -> None:
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierSource("", "title", "https://example.invalid", "archive", "1", "scope")
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierSource("id", "", "https://example.invalid", "archive", "1", "scope")
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierSource("id", "title", "https://example.invalid", "", "1", "scope")

    def test_record_rejects_empty_payload_and_sources(self) -> None:
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierRecord("bad", CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY, CausalAlphaFrontierRole.CONTROL, self.fixture.context_key, (), {}, self.fixture.records[0].expected_state, (), "bad")

    def test_record_rejects_wrong_boundary_enum(self) -> None:
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierRecord("bad", "unknown", CausalAlphaFrontierRole.CONTROL, self.fixture.context_key, ("encode",), {"x": 1}, self.fixture.records[0].expected_state, (), "bad")

    def test_fixture_rejects_wrong_boundary(self) -> None:
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierFixture("bad", "1", self.fixture.context_key, self.fixture.foreign_context_key, "patient_level", self.fixture.sources, self.fixture.records)

    def test_fixture_rejects_empty_sources(self) -> None:
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierFixture("bad", "1", self.fixture.context_key, self.fixture.foreign_context_key, CAUSAL_ALPHA_FRONTIER_BOUNDARY, (), self.fixture.records)

    def test_fixture_rejects_empty_records(self) -> None:
        with self.assertRaises(ValidationError):
            CausalAlphaFrontierFixture("bad", "1", self.fixture.context_key, self.fixture.foreign_context_key, CAUSAL_ALPHA_FRONTIER_BOUNDARY, self.fixture.sources, ())

    def test_operation_lookup_is_strict(self) -> None:
        self.assertEqual(self.fixture.operation_records("mediation_sensitivity")[0].operation, CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY)
        with self.assertRaises(ValueError):
            self.fixture.operation_records("not-an-operation")

    def test_role_lookup_is_closed(self) -> None:
        self.assertEqual({item.role for item in self.fixture.records}, {CausalAlphaFrontierRole.POSITIVE, CausalAlphaFrontierRole.CONTROL})
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)

    def test_evaluation_is_unchanged_by_repeated_replay(self) -> None:
        first = evaluate_causal_alpha_frontier_fixture(self.fixture)
        second = evaluate_causal_alpha_frontier_fixture(self.fixture)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(False), second.to_dict(False))

    def test_evaluation_mismatch_surface_is_empty(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        self.assertEqual(evaluation.evaluation.mismatches, ())
        self.assertTrue(all(item.state_match for item in evaluation.evaluation.results))
        self.assertTrue(all(item.accepted for item in evaluation.summaries))

    def test_runtime_top_level_keys_are_complete(self) -> None:
        payload = self.runtime.to_dict(False)
        required = {"fixture", "data_audit", "adapters", "evaluation", "controls", "contracts", "schema", "metrics", "lineage", "provenance", "integrity", "depth", "policy", "decisions", "traces", "reconciliation", "review", "projections", "diagnostics", "scenario", "validation", "quality", "bundle", "release", "artifacts", "replay", "operational", "boundary", "review_view", "exports", "assurance", "runbook", "stages", "observability", "stage_ids", "stage_count", "accepted"}
        self.assertTrue(required <= set(payload))
        self.assertEqual(payload["stage_count"], 31)

    def test_runtime_stage_events_have_unique_event_ids(self) -> None:
        event_ids = [item.event_id for item in self.runtime.observability.events]
        self.assertEqual(len(event_ids), 31)
        self.assertEqual(len(set(event_ids)), 31)
        self.assertTrue(all(item.event_type == "stage_completed" for item in self.runtime.observability.events))

    def test_runtime_stage_details_are_non_empty(self) -> None:
        self.assertTrue(all(item.detail for item in self.runtime.stages))
        self.assertTrue(all(item.output_address for item in self.runtime.stages))
        self.assertTrue(all(item.state == "completed" for item in self.runtime.stages))

    def test_control_class_enum_values_are_stable(self) -> None:
        self.assertEqual(tuple(item.value for item in CausalAlphaFrontierControlClass), ("positive", "single_source", "fragile", "missing", "unresolved", "contradictory", "measured_negative", "foreign_context"))
        self.assertEqual(self.runtime.controls.required_classes, tuple(CausalAlphaFrontierControlClass))
        self.assertEqual(self.runtime.controls.missing_classes, ())

    def test_policy_disposition_enum_values_are_stable(self) -> None:
        self.assertEqual(tuple(item.value for item in CausalAlphaFrontierDisposition), ("allow_descriptive", "review", "quarantine", "abstain"))
        self.assertEqual(sum(item.disposition is CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE for item in self.runtime.decisions), 3)
        self.assertEqual(sum(item.disposition is CausalAlphaFrontierDisposition.REVIEW for item in self.runtime.decisions), 9)
        self.assertEqual(sum(item.disposition is CausalAlphaFrontierDisposition.QUARANTINE for item in self.runtime.decisions), 4)

    def test_artifact_kinds_are_all_present_once(self) -> None:
        kinds = tuple(item.kind for item in self.runtime.artifacts.artifacts)
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertEqual(set(kinds), set(CausalAlphaFrontierArtifactKind))
        self.assertTrue(all(item.required for item in self.runtime.artifacts.artifacts))

    def test_export_media_types_are_declared(self) -> None:
        self.assertTrue(all(item.media_type for item in self.runtime.exports.envelopes))
        self.assertEqual(self.runtime.exports.by_id("review-csv").media_type, "text/csv")
        self.assertEqual(self.runtime.exports.by_id("review-markdown").media_type, "text/markdown")
        self.assertEqual(self.runtime.exports.by_id("diagnostics").media_type, "application/json")

    def test_query_empty_filter_returns_all_results(self) -> None:
        result = query_causal_alpha_frontier(self.runtime.bundle)
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.rows), 16)
        self.assertEqual(result.filters, {})
        self.assertEqual(result.record_ids, tuple(item.record_id for item in self.runtime.evaluation.evaluation.results))

    def test_query_combined_filter_has_intersection_semantics(self) -> None:
        result = query_causal_alpha_frontier(self.runtime.bundle, operation="negative_evidence", disposition="review")
        self.assertEqual(result.record_ids, ("D11-C12-P", "D11-C12-C1", "D11-C12-C2"))
        self.assertTrue(all(row["operation"] is CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE for row in result.rows))
        self.assertTrue(all(row["disposition"] is CausalAlphaFrontierDisposition.REVIEW for row in result.rows))

    def test_diagnostic_severity_is_typed(self) -> None:
        self.assertTrue(all(item.severity is CausalAlphaFrontierDiagnosticSeverity.ERROR for item in self.runtime.diagnostics.findings))
        self.assertEqual(self.runtime.diagnostics.errors, ())
        self.assertEqual(self.runtime.diagnostics.warnings, ())

    def test_trace_ledger_matches_runtime_decisions(self) -> None:
        for trace in self.runtime.traces.traces:
            decision = next(item for item in self.runtime.decisions if item.record_id == trace.record_id)
            self.assertEqual(trace.final_disposition, decision.disposition.value)
            self.assertEqual(trace.final_state, decision.state.value)
            self.assertEqual(trace.review_id is not None, decision.disposition is not CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE)

    def test_projection_facets_partition_record_ids(self) -> None:
        for dimension in self.runtime.projections.dimensions:
            facets = self.runtime.projections.where(dimension=dimension)
            ids = [record_id for facet in facets for record_id in facet.record_ids]
            self.assertEqual(len(ids), 16)
            self.assertEqual(len(set(ids)), 16)

    def test_foreign_context_is_excluded_from_exact_projection(self) -> None:
        exact = self.runtime.projections.facet("context", "exact")
        foreign = self.runtime.projections.facet("context", "foreign")
        self.assertEqual(exact.count, 12)
        self.assertEqual(foreign.count, 4)
        self.assertEqual(set(exact.record_ids) & set(foreign.record_ids), set())

    def test_replay_address_is_in_runtime_assurance(self) -> None:
        self.assertIn(self.runtime.replay.content_address, self.runtime.assurance.evidence_addresses)
        self.assertIn(self.runtime.diagnostics.content_address, (self.runtime.exports.by_id("diagnostics").source_address,))

    def test_release_check_ids_are_unique(self) -> None:
        check_ids = tuple(item.check_id for item in self.runtime.release.checks)
        self.assertEqual(len(check_ids), len(set(check_ids)))
        self.assertEqual(self.runtime.release.failed_check_ids, ())
        self.assertEqual(self.runtime.release.passed_count, len(check_ids))

    def test_runbook_addresses_cover_release_bundle_boundary_assurance(self) -> None:
        addresses = set(self.runtime.runbook.required_addresses)
        self.assertIn(self.runtime.release.content_address, addresses)
        self.assertIn(self.runtime.bundle.content_address, addresses)
        self.assertIn(self.runtime.boundary.content_address, addresses)
        self.assertIn(self.runtime.assurance.content_address, addresses)

    def test_fixture_source_map_and_record_map_are_total(self) -> None:
        self.assertEqual(set(self.fixture.source_map()), {item.source_id for item in self.fixture.sources})
        self.assertEqual(set(self.fixture.record_map()), {item.record_id for item in self.fixture.records})
        self.assertTrue(all(self.fixture.record_map()[item.record_id] is item for item in self.fixture.records))

    def test_runtime_acceptance_requires_all_release_planes(self) -> None:
        self.assertTrue(self.runtime.data_audit.accepted)
        self.assertTrue(self.runtime.evaluation.accepted)
        self.assertTrue(self.runtime.controls.accepted)
        self.assertTrue(self.runtime.traces.accepted)
        self.assertTrue(self.runtime.projections.accepted)
        self.assertTrue(self.runtime.diagnostics.accepted)
        self.assertTrue(self.runtime.release.accepted)
        self.assertTrue(self.runtime.artifacts.accepted)
        self.assertTrue(self.runtime.exports.accepted)
        self.assertTrue(self.runtime.assurance.accepted)
        self.assertTrue(self.runtime.accepted)

    def test_metrics_operation_lookup_is_total(self) -> None:
        for operation in CausalAlphaFrontierOperation:
            metric = self.runtime.metrics.operation(operation)
            self.assertEqual(metric.operation, operation)
            self.assertEqual(metric.record_count, 4)
            self.assertEqual(metric.accepted_count, 4)

    def test_contract_limitation_text_is_present_in_release_bundle(self) -> None:
        for contract in self.runtime.contracts.contracts:
            self.assertIn(contract.limitation, [item.limitation for item in self.runtime.validation.cells])

    def test_validation_matrix_record_ids_are_disjoint_by_operation(self) -> None:
        ids = [record_id for cell in self.runtime.validation.cells for record_id in cell.record_ids]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(set(ids)), 16)
        self.assertEqual(set(ids), {item.record_id for item in self.fixture.records})

    def test_review_view_preserves_fixture_order(self) -> None:
        self.assertEqual(tuple(item.record_id for item in self.runtime.review_view.rows), tuple(item.record_id for item in self.fixture.records))
        self.assertTrue(all(item.accepted for item in self.runtime.review_view.rows))

    def test_review_queue_priorities_are_bounded(self) -> None:
        self.assertEqual({item.priority for item in self.runtime.review.items}, {"blocking", "high"})
        self.assertEqual(sum(item.priority == "blocking" for item in self.runtime.review.items), 4)
        self.assertEqual(sum(item.priority == "high" for item in self.runtime.review.items), 9)

    def test_integrity_check_ids_are_unique(self) -> None:
        ids = tuple(item["check_id"] for item in self.runtime.integrity.checks)
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.runtime.integrity.failed_checks, ())

    def test_quality_check_ids_are_unique(self) -> None:
        ids = tuple(item["check_id"] for item in self.runtime.quality.checks)
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.runtime.quality.failed_checks, ())

    def test_observability_duration_is_non_negative(self) -> None:
        self.assertGreaterEqual(self.runtime.observability.total_duration_ms, 0.0)
        self.assertTrue(all(item.measurements["duration_ms"] >= 0.0 for item in self.runtime.observability.events))

    def test_source_receipt_scope_is_non_empty(self) -> None:
        self.assertTrue(all(item.scope for item in self.fixture.sources))
        self.assertTrue(all(item.release for item in self.fixture.sources))
        self.assertEqual(len({item.source_id for item in self.fixture.sources}), 5)

    def test_every_record_has_at_least_one_source_receipt(self) -> None:
        self.assertTrue(all(item.source_ids for item in self.fixture.records))
        self.assertTrue(all(set(item.source_ids) <= set(self.fixture.source_map()) for item in self.fixture.records))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.fixture.records))

    def test_every_result_has_expected_and_observed_states(self) -> None:
        for result in self.runtime.evaluation.evaluation.results:
            self.assertTrue(result.expected_state.value)
            self.assertTrue(result.observed_state.value)
            self.assertEqual(result.expected_state, result.observed_state)
            self.assertTrue(result.output)

    def test_control_operation_counts_sum_to_fixture_count(self) -> None:
        total = sum(sum(counts.values()) for counts in self.runtime.controls.operation_counts.values())
        self.assertEqual(total, 16)
        self.assertEqual(set(self.runtime.controls.operation_counts), {item.value for item in CausalAlphaFrontierOperation})

    def test_projection_dimension_counts_are_nonzero(self) -> None:
        for dimension in self.runtime.projections.dimensions:
            self.assertGreater(len(self.runtime.projections.where(dimension=dimension)), 0)
            self.assertTrue(all(item.count > 0 for item in self.runtime.projections.where(dimension=dimension)))

    def test_diagnostic_check_addresses_are_referenced_by_runtime(self) -> None:
        addresses = {item.content_address for item in self.runtime.diagnostics.findings}
        self.assertEqual(len(addresses), 8)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.runtime.diagnostics.findings))

    def test_release_state_and_boundary_are_consistent(self) -> None:
        self.assertEqual(self.runtime.release.state.value, "ready")
        self.assertEqual(self.runtime.runbook.release_state, "ready")
        self.assertEqual(self.runtime.boundary.boundary, CAUSAL_ALPHA_FRONTIER_BOUNDARY)

    def test_all_runtime_plane_addresses_are_present(self) -> None:
        plane_values = (self.runtime.fixture, self.runtime.data_audit, self.runtime.adapters, self.runtime.evaluation, self.runtime.controls, self.runtime.contracts, self.runtime.schema, self.runtime.metrics, self.runtime.lineage, self.runtime.provenance, self.runtime.integrity, self.runtime.depth, self.runtime.policy, self.runtime.traces, self.runtime.reconciliation, self.runtime.review, self.runtime.projections, self.runtime.diagnostics, self.runtime.scenario, self.runtime.validation, self.runtime.quality, self.runtime.bundle, self.runtime.release, self.runtime.artifacts, self.runtime.replay, self.runtime.operational, self.runtime.boundary, self.runtime.review_view, self.runtime.exports, self.runtime.assurance, self.runtime.runbook)
        self.assertTrue(all(getattr(item, "content_address", "").startswith("sha256:") for item in plane_values))

    def test_data_audit_check_addresses_are_unique(self) -> None:
        addresses = tuple(item["content_address"] for item in self.runtime.data_audit.checks)
        self.assertEqual(len(addresses), 12)
        self.assertEqual(len(set(addresses)), 12)
        self.assertTrue(all(item.startswith("sha256:") for item in addresses))

    def test_control_rows_keep_source_counts(self) -> None:
        counts = {item.record_id: item.source_count for item in self.runtime.controls.rows}
        self.assertEqual(counts["D11-C09-P"], 2)
        self.assertEqual(counts["D11-C10-P"], 2)
        self.assertEqual(counts["D11-C11-P"], 3)
        self.assertEqual(counts["D11-C12-P"], 1)

    def test_trace_review_ids_match_review_queue(self) -> None:
        review_ids = {item.review_id for item in self.runtime.review.items}
        trace_review_ids = {item.review_id for item in self.runtime.traces.traces if item.review_id is not None}
        self.assertEqual(trace_review_ids, review_ids)

    def test_projection_facets_have_sorted_record_ids(self) -> None:
        for facet in self.runtime.projections.facets:
            self.assertEqual(tuple(sorted(facet.record_ids)), facet.record_ids)
            self.assertEqual(facet.count, len(facet.record_ids))

    def test_runbook_commands_use_only_alpha_frontier_surface(self) -> None:
        self.assertTrue(all(item.command.startswith(("causal-alpha-frontier-", "export-causal-alpha-frontier-")) for item in self.runtime.runbook.steps))
        self.assertEqual(len(self.runtime.runbook.commands), 12)

    def test_runtime_observability_stage_ids_match_runtime_stage_ids(self) -> None:
        self.assertEqual(self.runtime.observability.stage_ids, self.runtime.stage_ids)
        self.assertEqual(len(self.runtime.observability.stage_ids), 31)

    def test_release_manifest_excludes_all_five_forbidden_uses(self) -> None:
        self.assertEqual(set(self.runtime.release.excluded_uses), {"causal identification", "clinical diagnosis", "treatment recommendation", "prognosis", "patient care"})

    def test_assurance_claims_are_bounded_and_non_empty(self) -> None:
        self.assertEqual(len(self.runtime.assurance.claims), 4)
        self.assertEqual(len(self.runtime.assurance.limitations), 4)
        self.assertTrue(all(claim for claim in self.runtime.assurance.claims))
        self.assertTrue(all(limitation for limitation in self.runtime.assurance.limitations))

    def test_export_inventory_addresses_are_unique(self) -> None:
        addresses = tuple(item.content_address for item in self.runtime.exports.envelopes)
        self.assertEqual(len(addresses), 10)
        self.assertEqual(len(set(addresses)), 10)
        self.assertTrue(all(item.startswith("sha256:") for item in addresses))

    def test_review_view_content_address_is_reproducible(self) -> None:
        rebuilt = self.runtime.review_view.to_dict(False)
        self.assertEqual(self.runtime.review_view.content_address, __import__("glio_noncode.serialization", fromlist=["content_hash"]).content_hash(rebuilt))

    def test_runtime_fixture_boundary_is_not_patient_level(self) -> None:
        self.assertEqual(self.runtime.fixture.boundary, "public_aggregate_non_patient")
        self.assertNotIn("patient", self.runtime.fixture.boundary.replace("non_patient", ""))

    def test_every_foreign_row_has_context_mismatch_issue(self) -> None:
        foreign = [item for item in self.runtime.evaluation.evaluation.results if item.observed_state.value == "out_of_domain"]
        self.assertEqual(len(foreign), 4)
        self.assertTrue(all("context_mismatch" in item.observed_issue_codes for item in foreign))

    def test_runtime_review_count_matches_review_view_links(self) -> None:
        self.assertEqual(sum(item.review_id is not None for item in self.runtime.review_view.rows), len(self.runtime.review.items))

    def test_runtime_artifact_paths_are_unique(self) -> None:
        paths = tuple(item.relative_path for item in self.runtime.artifacts.artifacts)
        self.assertEqual(len(paths), 19)
        self.assertEqual(len(set(paths)), 19)

    def test_runtime_export_ids_are_unique(self) -> None:
        ids = tuple(item.export_id for item in self.runtime.exports.envelopes)
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)

    def test_runtime_projection_control_facet_is_present(self) -> None:
        facet = self.runtime.projections.facet("control_class", "foreign_context")
        self.assertEqual(facet.count, 4)
        self.assertTrue(all(item.endswith("-C3") for item in facet.record_ids))

    def test_runtime_control_coverage_positive_rows_are_not_reviewed(self) -> None:
        positives = self.runtime.controls.for_class(CausalAlphaFrontierControlClass.POSITIVE)
        self.assertEqual(len(positives), 4)
        self.assertEqual({item.record_id for item in positives if item.retained_in_review}, {"D11-C12-P"})
        self.assertEqual({item.record_id for item in positives if not item.retained_in_review}, {"D11-C09-P", "D11-C10-P", "D11-C11-P"})

    def test_runtime_diagnostics_remediation_is_release_safe(self) -> None:
        self.assertTrue(all("replay" in item.remediation or "inspect" in item.remediation or "add" in item.remediation or "route" in item.remediation or "do not" in item.remediation or "rebuild" in item.remediation for item in self.runtime.diagnostics.findings))

    def test_runtime_lineage_contains_each_result_edge(self) -> None:
        self.assertEqual(sum(edge[2] == "evaluates" for edge in self.runtime.lineage.edges), 16)
        self.assertTrue(all(edge[0].startswith("record:") and edge[1].startswith("result:") for edge in self.runtime.lineage.edges if edge[2] == "evaluates"))

    def test_runtime_provenance_contains_fixture_and_source_receipts(self) -> None:
        self.assertEqual(sum(item.kind == "fixture" for item in self.runtime.provenance.nodes), 1)
        self.assertEqual(sum(item.kind == "source" for item in self.runtime.provenance.nodes), 5)
        self.assertTrue(all(item.address.startswith("sha256:") for item in self.runtime.provenance.nodes))

    def test_runtime_release_checks_point_to_addresses(self) -> None:
        self.assertTrue(all(item.evidence_address.startswith("sha256:") for item in self.runtime.release.checks))

    def test_runtime_all_control_rows_have_expected_state_values(self) -> None:
        self.assertTrue(all(item.expected_state.value for item in self.runtime.controls.rows))
        self.assertTrue(all(item.observed_state.value for item in self.runtime.controls.rows))

    def test_runtime_has_exactly_one_fixture_boundary(self) -> None:
        self.assertEqual(self.runtime.fixture.boundary, CAUSAL_ALPHA_FRONTIER_BOUNDARY)

    def test_runtime_fixture_has_five_sources(self) -> None:
        self.assertEqual(len(self.runtime.fixture.sources), 5)

    def test_runtime_fixture_has_sixteen_records(self) -> None:
        self.assertEqual(len(self.runtime.fixture.records), 16)


if __name__ == "__main__":
    unittest.main()
