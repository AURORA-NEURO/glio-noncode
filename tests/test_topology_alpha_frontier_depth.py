from __future__ import annotations

import unittest

from glio_noncode.topology_alpha_frontier_acceptance import evaluate_topology_alpha_frontier_acceptance
from glio_noncode.topology_alpha_frontier_assurance import build_topology_alpha_frontier_assurance
from glio_noncode.topology_alpha_frontier_artifact_checks import audit_topology_alpha_frontier_artifacts
from glio_noncode.topology_alpha_frontier_audit_log import build_topology_alpha_frontier_audit_log
from glio_noncode.topology_alpha_frontier_benchmark import benchmark_topology_alpha_frontier
from glio_noncode.topology_alpha_frontier_claim_boundary import allowed_topology_alpha_frontier_claims, build_topology_alpha_frontier_claim_boundary
from glio_noncode.topology_alpha_frontier_checksum_audit import audit_topology_alpha_frontier_checksums
from glio_noncode.topology_alpha_frontier_composite import build_topology_alpha_frontier_composite
from glio_noncode.topology_alpha_frontier_conformance import build_topology_alpha_frontier_conformance
from glio_noncode.topology_alpha_frontier_comparison import build_topology_alpha_frontier_comparisons
from glio_noncode.topology_alpha_frontier_data_dictionary import build_topology_alpha_frontier_data_dictionary
from glio_noncode.topology_alpha_frontier_evidence_matrix import build_topology_alpha_frontier_evidence_matrix, summarize_topology_alpha_frontier_evidence_matrix
from glio_noncode.topology_alpha_frontier_failure_catalog import build_topology_alpha_frontier_failure_catalog, classify_topology_alpha_frontier_issues
from glio_noncode.topology_alpha_frontier_fixture_eval import evaluate_topology_alpha_frontier_fixture
from glio_noncode.topology_alpha_frontier_governance import build_topology_alpha_frontier_governance
from glio_noncode.topology_alpha_frontier_history import build_topology_alpha_frontier_history
from glio_noncode.topology_alpha_frontier_inspection import inspect_topology_alpha_frontier
from glio_noncode.topology_alpha_frontier_lineage_audit import audit_topology_alpha_frontier_lineage
from glio_noncode.topology_alpha_frontier_manifest_serialization import address_topology_alpha_frontier_payload, canonical_topology_alpha_frontier_json, serialize_topology_alpha_frontier_record
from glio_noncode.topology_alpha_frontier_control_catalog import build_topology_alpha_frontier_control_catalog
from glio_noncode.topology_alpha_frontier_mutations import mutate_topology_alpha_frontier_context, mutate_topology_alpha_frontier_expected_state, mutate_topology_alpha_frontier_issue_floor, summarize_topology_alpha_frontier_mutation
from glio_noncode.topology_alpha_frontier_operator_handbook import default_topology_alpha_frontier_operator_handbook
from glio_noncode.topology_alpha_frontier_packaging import build_topology_alpha_frontier_package_manifest
from glio_noncode.topology_alpha_frontier_partition import build_topology_alpha_frontier_partitions
from glio_noncode.topology_alpha_frontier_pipeline import run_topology_alpha_frontier_pipeline
from glio_noncode.topology_alpha_frontier_field_projection import default_topology_alpha_frontier_projections, project_topology_alpha_frontier_rows
from glio_noncode.topology_alpha_frontier_query_plan import default_topology_alpha_frontier_query_plans, execute_topology_alpha_frontier_query_plan
from glio_noncode.topology_alpha_frontier_queries import TopologyAlphaFrontierQuery, query_many_topology_alpha_frontier, query_topology_alpha_frontier
from glio_noncode.topology_alpha_frontier_regression import run_topology_alpha_frontier_regression
from glio_noncode.topology_alpha_frontier_release_notes import build_topology_alpha_frontier_release_notes, render_topology_alpha_frontier_release_notes
from glio_noncode.topology_alpha_frontier_release_gate import evaluate_topology_alpha_frontier_release_gate
from glio_noncode.topology_alpha_frontier_report_render import build_and_render_topology_alpha_frontier_validation, render_topology_alpha_frontier_assurance_summary, render_topology_alpha_frontier_pipeline_summary
from glio_noncode.topology_alpha_frontier_replay_ledger import build_topology_alpha_frontier_replay_ledger, compare_topology_alpha_frontier_ledgers
from glio_noncode.topology_alpha_frontier_resource_limits import audit_topology_alpha_frontier_resources
from glio_noncode.topology_alpha_frontier_review_actions import build_topology_alpha_frontier_review_actions
from glio_noncode.topology_alpha_frontier_scorecard import build_topology_alpha_frontier_scorecards
from glio_noncode.topology_alpha_frontier_source_checks import build_topology_alpha_frontier_source_checks
from glio_noncode.topology_alpha_frontier_source_registry import build_topology_alpha_frontier_source_registry
from glio_noncode.topology_alpha_frontier_state_transitions import audit_topology_alpha_frontier_state_transitions
from glio_noncode.topology_alpha_frontier_scenario_runner import run_topology_alpha_frontier_scenarios
from glio_noncode.topology_alpha_frontier_validation_report import build_topology_alpha_frontier_validation_report
from glio_noncode.topology_alpha_frontier_public_data import default_topology_alpha_frontier_fixture


class TopologyAlphaFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_alpha_frontier_fixture()
        self.evaluation = evaluate_topology_alpha_frontier_fixture(self.fixture)

    def test_evidence_matrix_is_complete(self) -> None:
        matrix = build_topology_alpha_frontier_evidence_matrix(self.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(matrix.operation_count, 4)
        self.assertEqual(matrix.record_count, 16)
        self.assertEqual(matrix.review_count, 12)
        self.assertEqual(summarize_topology_alpha_frontier_evidence_matrix(matrix)["states"]["supported"], 4)

    def test_claim_boundary_has_allowed_and_blocked_statements(self) -> None:
        report = build_topology_alpha_frontier_claim_boundary(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.allowed_count, 16)
        self.assertEqual(report.blocked_count, 16)
        self.assertEqual(len(allowed_topology_alpha_frontier_claims(report)), 4)
        self.assertIn("orientation", report.for_operation("boundary_motif")[0].allowed_statement)

    def test_failure_catalog_covers_every_observed_issue(self) -> None:
        catalog = build_topology_alpha_frontier_failure_catalog(self.evaluation)
        self.assertTrue(catalog.accepted)
        self.assertIn("context_mismatch", catalog.observed_codes)
        self.assertIn("disagreement", classify_topology_alpha_frontier_issues(catalog))
        self.assertEqual(catalog.for_code("unknown_edge_id").state_effect, "partial")

    def test_conformance_preserves_declared_operation_fields(self) -> None:
        report = build_topology_alpha_frontier_conformance(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 16)
        self.assertEqual(report.failed(), ())
        self.assertIn("methylation_fraction", {item.field_name for item in report.fields["idh_insulator"]})

    def test_source_receipt_checks_are_closed(self) -> None:
        registry = build_topology_alpha_frontier_source_registry(self.fixture)
        report = build_topology_alpha_frontier_source_checks(self.fixture, self.evaluation)
        self.assertTrue(registry.accepted)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 17)
        self.assertEqual(report.failed(), ())

    def test_benchmark_has_four_bounded_cases(self) -> None:
        report = benchmark_topology_alpha_frontier(self.fixture, repetitions=1)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.cases), 4)
        self.assertEqual(report.total_rows, 64)
        self.assertEqual(report.for_operation("sv_rewire").record_count, 16)

    def test_composite_view_keeps_operation_outputs_separate(self) -> None:
        report = build_topology_alpha_frontier_composite(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.operations), 4)
        self.assertEqual(len(report.cross_operation_links), 3)
        self.assertTrue(all(item.descriptive_only for item in report.operations))

    def test_query_filters_are_deterministic(self) -> None:
        supported = query_topology_alpha_frontier(self.evaluation, TopologyAlphaFrontierQuery("supported", state="supported"))
        controls = query_topology_alpha_frontier(self.evaluation, TopologyAlphaFrontierQuery("controls", role="control"))
        foreign = query_topology_alpha_frontier(self.evaluation, TopologyAlphaFrontierQuery("foreign", issue_code="context_mismatch"))
        self.assertTrue(supported.accepted)
        self.assertEqual(supported.total_matches, 4)
        self.assertEqual(controls.total_matches, 12)
        self.assertEqual(foreign.total_matches, 4)
        self.assertEqual(len(query_many_topology_alpha_frontier(self.evaluation, (supported.query, controls.query))), 2)

    def test_inspection_view_exposes_dispositions(self) -> None:
        report = inspect_topology_alpha_frontier(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(inspect_topology_alpha_frontier(self.evaluation, role="positive").items), 4)
        self.assertEqual(len(inspect_topology_alpha_frontier(self.evaluation, state="out_of_domain").items), 4)
        self.assertEqual(report.matched_count, 16)
        self.assertTrue(all(item.disposition for item in report.items))

    def test_replay_ledger_has_ordered_stage_receipts(self) -> None:
        first = build_topology_alpha_frontier_replay_ledger(run_topology_alpha_frontier_pipeline(self.fixture))
        second = build_topology_alpha_frontier_replay_ledger(run_topology_alpha_frontier_pipeline(self.fixture))
        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(len(first.entries), 12)
        self.assertEqual(first.entry("evaluation").sequence, 4)
        comparison = compare_topology_alpha_frontier_ledgers(first, second)
        self.assertTrue(comparison["same_stages"])
        self.assertTrue(comparison["accepted"])

    def test_governance_and_acceptance_compose_all_assurance_planes(self) -> None:
        pipeline = run_topology_alpha_frontier_pipeline(self.fixture)
        evidence = build_topology_alpha_frontier_evidence_matrix(self.evaluation)
        claims = build_topology_alpha_frontier_claim_boundary(self.evaluation)
        conformance = build_topology_alpha_frontier_conformance(self.fixture, self.evaluation)
        failures = build_topology_alpha_frontier_failure_catalog(self.evaluation)
        sources = build_topology_alpha_frontier_source_checks(self.fixture, self.evaluation)
        governance = build_topology_alpha_frontier_governance(self.evaluation)
        acceptance = evaluate_topology_alpha_frontier_acceptance(self.evaluation, evidence, claims, conformance, failures, sources)
        self.assertTrue(pipeline.accepted)
        self.assertTrue(governance.accepted)
        self.assertTrue(acceptance.accepted)
        self.assertEqual(acceptance.failed(), ())

    def test_regression_history_and_package_metadata_are_stable(self) -> None:
        pipeline = run_topology_alpha_frontier_pipeline(self.fixture)
        regression = run_topology_alpha_frontier_regression(self.fixture)
        history = build_topology_alpha_frontier_history()
        package = build_topology_alpha_frontier_package_manifest(pipeline)
        notes = build_topology_alpha_frontier_release_notes(pipeline)
        self.assertTrue(regression.accepted)
        self.assertTrue(history.accepted)
        self.assertEqual(history.latest().record_count, 16)
        self.assertTrue(package.accepted)
        self.assertEqual(len(package.required_files()), 7)
        self.assertTrue(notes.accepted)
        self.assertIn("Aggregate boundary", render_topology_alpha_frontier_release_notes(notes))

    def test_data_dictionary_and_state_transitions_are_locked(self) -> None:
        dictionary = build_topology_alpha_frontier_data_dictionary()
        transitions = audit_topology_alpha_frontier_state_transitions(self.evaluation)
        self.assertTrue(dictionary.accepted)
        self.assertEqual(dictionary.operation_count, 4)
        self.assertEqual(dictionary.field_count, 24)
        self.assertIn("methylation_fraction", dictionary.required_fields("idh_insulator"))
        self.assertTrue(transitions.accepted)
        self.assertEqual(len(transitions.vocabulary), 7)
        self.assertEqual(len(transitions.for_state("out_of_domain")), 4)

    def test_lineage_checksums_and_comparisons_close_the_graph(self) -> None:
        lineage = audit_topology_alpha_frontier_lineage(self.fixture, self.evaluation)
        checksums = audit_topology_alpha_frontier_checksums(self.fixture, self.evaluation)
        comparisons = build_topology_alpha_frontier_comparisons(self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertGreaterEqual(len(lineage.checks), 32)
        self.assertTrue(checksums.accepted)
        self.assertEqual(checksums.checked_count, 21)
        self.assertTrue(comparisons.accepted)
        self.assertEqual(len(comparisons.comparisons), 12)
        self.assertEqual(comparisons.operation_count, 4)

    def test_scorecards_partitions_actions_and_resources_are_bounded(self) -> None:
        pipeline = run_topology_alpha_frontier_pipeline(self.fixture)
        scorecards = build_topology_alpha_frontier_scorecards(self.evaluation)
        partitions = build_topology_alpha_frontier_partitions(self.evaluation)
        actions = build_topology_alpha_frontier_review_actions(self.evaluation)
        resources = audit_topology_alpha_frontier_resources(self.evaluation, pipeline)
        self.assertTrue(scorecards.accepted)
        self.assertEqual(scorecards.aggregate_record_count, 16)
        self.assertEqual(scorecards.for_operation("ctcf_cohesin").control_count, 3)
        self.assertTrue(partitions.accepted)
        self.assertEqual(partitions.covered_record_count, 16)
        self.assertEqual(len(partitions.for_dimension("operation")), 4)
        self.assertTrue(actions.accepted)
        self.assertEqual(actions.open_count, 16)
        self.assertTrue(resources.accepted)
        self.assertEqual(resources.check("records").observed, 16)

    def test_release_gate_audit_log_and_handbook_are_operational(self) -> None:
        pipeline = run_topology_alpha_frontier_pipeline(self.fixture)
        gate = evaluate_topology_alpha_frontier_release_gate(pipeline)
        log = build_topology_alpha_frontier_audit_log(pipeline)
        handbook = default_topology_alpha_frontier_operator_handbook()
        self.assertTrue(gate.publishable)
        self.assertEqual(gate.blocking_failures, ())
        self.assertTrue(log.accepted)
        self.assertEqual(len(log.events), 12)
        self.assertEqual(log.tail().sequence, 12)
        self.assertTrue(handbook.accepted)
        self.assertEqual(len(handbook.procedures), 5)

    def test_assurance_report_composes_every_new_surface(self) -> None:
        report = build_topology_alpha_frontier_assurance(run_topology_alpha_frontier_pipeline(self.fixture))
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed(), ())
        self.assertEqual(len(report.checks), 12)
        self.assertEqual(report.dictionary.field_count, 24)
        self.assertEqual(report.actions.open_count, 16)
        self.assertEqual(report.release_gate.blocking_failures, ())

    def test_canonical_serialization_is_stable_and_addressable(self) -> None:
        payload = {"operation": "boundary_motif", "record_id": "D09-C09-P", "state": "supported"}
        first = canonical_topology_alpha_frontier_json(payload)
        second = canonical_topology_alpha_frontier_json(dict(reversed(tuple(payload.items()))))
        serialized = serialize_topology_alpha_frontier_record(payload)
        self.assertEqual(first, second)
        self.assertTrue(address_topology_alpha_frontier_payload(payload).startswith("sha256:"))
        self.assertTrue(serialized["content_address"].startswith("sha256:"))

    def test_control_catalog_and_artifact_checks_are_complete(self) -> None:
        pipeline = run_topology_alpha_frontier_pipeline(self.fixture)
        controls = build_topology_alpha_frontier_control_catalog(self.evaluation)
        artifacts = audit_topology_alpha_frontier_artifacts(pipeline)
        self.assertTrue(controls.accepted)
        self.assertEqual(controls.control_count, 12)
        self.assertEqual(len(controls.for_kind("foreign_context")), 4)
        self.assertTrue(artifacts.accepted)
        self.assertEqual(artifacts.checked_count, 20)
        self.assertEqual(len(artifacts.failed()), 0)

    def test_mutation_scenarios_preserve_explicit_failure_semantics(self) -> None:
        state = evaluate_topology_alpha_frontier_fixture(mutate_topology_alpha_frontier_expected_state(self.fixture))
        issue = evaluate_topology_alpha_frontier_fixture(mutate_topology_alpha_frontier_issue_floor(self.fixture))
        context = evaluate_topology_alpha_frontier_fixture(mutate_topology_alpha_frontier_context(self.fixture))
        scenarios = run_topology_alpha_frontier_scenarios(self.fixture)
        self.assertFalse(state.accepted)
        self.assertFalse(issue.accepted)
        self.assertFalse(context.accepted)
        self.assertTrue(scenarios.accepted)
        self.assertEqual(len(scenarios.scenarios), 3)

    def test_validation_and_text_renderers_are_stable(self) -> None:
        pipeline = run_topology_alpha_frontier_pipeline(self.fixture)
        validation = build_topology_alpha_frontier_validation_report(pipeline)
        assurance = build_topology_alpha_frontier_assurance(pipeline)
        self.assertTrue(validation.accepted)
        self.assertEqual(len(validation.sections), 6)
        self.assertIn("accepted=true", build_and_render_topology_alpha_frontier_validation(pipeline))
        self.assertIn("stage.evaluation=passed", render_topology_alpha_frontier_pipeline_summary(pipeline))
        self.assertIn("checks=12", render_topology_alpha_frontier_assurance_summary(assurance))

    def test_query_plans_and_public_projections_are_reusable(self) -> None:
        plans = default_topology_alpha_frontier_query_plans()
        projections = default_topology_alpha_frontier_projections()
        controls = execute_topology_alpha_frontier_query_plan(self.evaluation, plans[0])
        foreign = execute_topology_alpha_frontier_query_plan(self.evaluation, plans[1])
        positives = execute_topology_alpha_frontier_query_plan(self.evaluation, plans[2])
        review = project_topology_alpha_frontier_rows(self.evaluation.rows, projections[0])
        lineage = project_topology_alpha_frontier_rows(self.evaluation.rows, projections[2])
        self.assertEqual(controls.matched_count, 12)
        self.assertEqual(foreign.matched_count, 4)
        self.assertEqual(positives.matched_count, 4)
        self.assertTrue(controls.accepted and foreign.accepted and positives.accepted)
        self.assertTrue(review.accepted and lineage.accepted)
        self.assertEqual(len(review.rows), 16)
        self.assertNotIn("subject_id", review.rows[0])

    def test_query_plan_limits_and_projection_addresses_are_enforced(self) -> None:
        plan = default_topology_alpha_frontier_query_plans()[0]
        limited = execute_topology_alpha_frontier_query_plan(self.evaluation, type(plan)(plan.plan_id, plan.title, plan.predicates, plan.projection, plan.sort_fields, 2, plan.purpose, plan.accepted))
        projection = default_topology_alpha_frontier_projections()[1]
        result = project_topology_alpha_frontier_rows(self.evaluation.rows[:2], projection)
        self.assertEqual(limited.matched_count, 12)
        self.assertEqual(len(limited.rows), 2)
        self.assertTrue(limited.truncated)
        self.assertTrue(result.content_address.startswith("sha256:"))

    def test_mutation_addresses_change_without_changing_fixture_cardinality(self) -> None:
        original = self.fixture.content_address
        mutated = mutate_topology_alpha_frontier_context(self.fixture)
        summary = summarize_topology_alpha_frontier_mutation(mutated)
        self.assertNotEqual(original, mutated.content_address)
        self.assertEqual(summary["record_count"], 16)
        self.assertEqual(summary["source_count"], 4)
        self.assertNotEqual(summary["record_addresses"]["D09-C12-P"], self.fixture.records[12].content_address)

    def test_control_catalog_preserves_operation_balance(self) -> None:
        catalog = build_topology_alpha_frontier_control_catalog(self.evaluation)
        self.assertEqual([len(catalog.for_operation(name)) for name in ("boundary_motif", "ctcf_cohesin", "idh_insulator", "sv_rewire")], [3, 3, 3, 3])
        self.assertEqual(len(catalog.for_kind("disagreement")), 2)
        self.assertEqual(len(catalog.for_kind("missing_or_invalid")), 6)

    def test_rendered_pipeline_summary_contains_every_stage(self) -> None:
        pipeline = run_topology_alpha_frontier_pipeline(self.fixture)
        rendered = render_topology_alpha_frontier_pipeline_summary(pipeline)
        for stage in pipeline.stages:
            self.assertIn(f"stage.{stage.stage_id}=passed", rendered)

    def test_release_gate_categories_remain_explicit(self) -> None:
        gate = evaluate_topology_alpha_frontier_release_gate(run_topology_alpha_frontier_pipeline(self.fixture))
        self.assertEqual(len(gate.by_category("execution")), 1)
        self.assertEqual(len(gate.by_category("advisory")), 2)
        self.assertEqual(gate.failed(), ())


if __name__ == "__main__":
    unittest.main()
