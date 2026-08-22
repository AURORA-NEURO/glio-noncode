from __future__ import annotations

import unittest

from glio_noncode.causal_alpha_frontier_adapters import (
    build_causal_alpha_frontier_adapters,
    evaluate_causal_alpha_frontier_fixture,
)
from glio_noncode.causal_alpha_frontier_artifacts import build_causal_alpha_frontier_artifact_inventory
from glio_noncode.causal_alpha_frontier_assurance import build_causal_alpha_frontier_assurance
from glio_noncode.causal_alpha_frontier_bundle import assemble_causal_alpha_frontier_bundle
from glio_noncode.causal_alpha_frontier_claim_boundary import build_causal_alpha_frontier_claim_boundary
from glio_noncode.causal_alpha_frontier_contracts import build_causal_alpha_frontier_contracts
from glio_noncode.causal_alpha_frontier_depth import audit_causal_alpha_frontier_depth
from glio_noncode.causal_alpha_frontier_exports import build_causal_alpha_frontier_exports
from glio_noncode.causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from glio_noncode.causal_alpha_frontier_integrity import evaluate_causal_alpha_frontier_integrity
from glio_noncode.causal_alpha_frontier_lineage import build_causal_alpha_frontier_lineage
from glio_noncode.causal_alpha_frontier_metrics import build_causal_alpha_frontier_metrics
from glio_noncode.causal_alpha_frontier_operational import build_causal_alpha_frontier_operational_matrix
from glio_noncode.causal_alpha_frontier_policy import default_causal_alpha_frontier_policy
from glio_noncode.causal_alpha_frontier_provenance import build_causal_alpha_frontier_provenance
from glio_noncode.causal_alpha_frontier_public_data import (
    CAUSAL_ALPHA_FRONTIER_BOUNDARY,
    CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY,
    CAUSAL_ALPHA_FRONTIER_FIXTURE_VERSION,
    CAUSAL_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY,
    CausalAlphaFrontierOperation,
    CausalAlphaFrontierRole,
    audit_causal_alpha_frontier_data,
    default_causal_alpha_frontier_fixture,
)
from glio_noncode.causal_alpha_frontier_quality_gate import evaluate_causal_alpha_frontier_quality
from glio_noncode.causal_alpha_frontier_query import query_causal_alpha_frontier
from glio_noncode.causal_alpha_frontier_reconciliation import reconcile_causal_alpha_frontier
from glio_noncode.causal_alpha_frontier_release import build_causal_alpha_frontier_release_manifest
from glio_noncode.causal_alpha_frontier_replay import replay_causal_alpha_frontier
from glio_noncode.causal_alpha_frontier_review import build_causal_alpha_frontier_review_queue
from glio_noncode.causal_alpha_frontier_runbook import build_causal_alpha_frontier_runbook, runbook_is_executable
from glio_noncode.causal_alpha_frontier_runtime import run_causal_alpha_frontier_runtime
from glio_noncode.causal_alpha_frontier_scenario_matrix import build_causal_alpha_frontier_scenario_matrix
from glio_noncode.causal_alpha_frontier_schema import validate_causal_alpha_frontier_schema
from glio_noncode.causal_alpha_frontier_validation_matrix import build_causal_alpha_frontier_validation_matrix
from glio_noncode.causal_alpha_frontier_views import build_causal_alpha_frontier_review_view
from glio_noncode.causal_reasoning import CausalState


class CausalAlphaFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_alpha_frontier_fixture()

    def test_fixture_is_pinned_to_public_aggregate_boundary(self) -> None:
        self.assertEqual(self.fixture.version, CAUSAL_ALPHA_FRONTIER_FIXTURE_VERSION)
        self.assertEqual(self.fixture.context_key, CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.foreign_context_key, CAUSAL_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY)
        self.assertEqual(self.fixture.boundary, CAUSAL_ALPHA_FRONTIER_BOUNDARY)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(len(self.fixture.record_map()), 16)
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.fixture.records))

    def test_fixture_has_four_rows_per_operation(self) -> None:
        for operation in CausalAlphaFrontierOperation:
            rows = self.fixture.operation_records(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role is CausalAlphaFrontierRole.POSITIVE for item in rows), 1)
            self.assertEqual(sum(item.role is CausalAlphaFrontierRole.CONTROL for item in rows), 3)

    def test_data_audit_is_accepted(self) -> None:
        audit = audit_causal_alpha_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.failed_checks, ())
        self.assertEqual(audit.foreign_context_count, 4)
        self.assertEqual(len(audit.checks), 12)

    def test_adapter_registry_is_closed(self) -> None:
        registry = build_causal_alpha_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.adapters), 4)
        self.assertEqual({item.operation for item in registry.adapters}, set(CausalAlphaFrontierOperation))
        self.assertIn("MediationSensitivityAnalyzer", registry.for_operation("mediation_sensitivity").implementation)

    def test_low_level_evaluation_matches_all_expected_states(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture(self.fixture)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(len(evaluation.results), 16)
        self.assertEqual(evaluation.mismatches, ())
        self.assertEqual(
            {item.record_id: item.observed_state for item in evaluation.results},
            {
                "D11-C09-P": CausalState.SUPPORTED,
                "D11-C09-C1": CausalState.PARTIAL,
                "D11-C09-C2": CausalState.PARTIAL,
                "D11-C09-C3": CausalState.OUT_OF_DOMAIN,
                "D11-C10-P": CausalState.SUPPORTED,
                "D11-C10-C1": CausalState.PARTIAL,
                "D11-C10-C2": CausalState.PARTIAL,
                "D11-C10-C3": CausalState.OUT_OF_DOMAIN,
                "D11-C11-P": CausalState.SUPPORTED,
                "D11-C11-C1": CausalState.PARTIAL,
                "D11-C11-C2": CausalState.CONTRADICTORY,
                "D11-C11-C3": CausalState.OUT_OF_DOMAIN,
                "D11-C12-P": CausalState.PARTIAL,
                "D11-C12-C1": CausalState.MEASURED_NEGATIVE,
                "D11-C12-C2": CausalState.CONTRADICTORY,
                "D11-C12-C3": CausalState.OUT_OF_DOMAIN,
            },
        )

    def test_deep_evaluation_summarizes_each_operation(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(len(evaluation.summaries), 4)
        for summary in evaluation.summaries:
            self.assertEqual(summary.record_count, 4)
            self.assertEqual(summary.accepted_count, 4)
            self.assertTrue(summary.accepted)
            self.assertIn("out_of_domain", summary.states)
            self.assertIn("context_mismatch", summary.issue_codes)

    def test_contracts_schema_and_metrics_close(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        contracts = build_causal_alpha_frontier_contracts()
        schema = validate_causal_alpha_frontier_schema(self.fixture, evaluation.evaluation, contracts)
        metrics = build_causal_alpha_frontier_metrics(self.fixture, evaluation)
        self.assertTrue(contracts.accepted)
        self.assertTrue(schema.accepted)
        self.assertTrue(metrics.accepted)
        self.assertEqual(metrics.total_records, 16)
        self.assertEqual(metrics.accepted_records, 16)
        self.assertEqual(metrics.foreign_records, 4)
        self.assertEqual([item.record_count for item in metrics.operations], [4, 4, 4, 4])

    def test_lineage_and_provenance_close(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        lineage = build_causal_alpha_frontier_lineage(self.fixture, evaluation)
        provenance = build_causal_alpha_frontier_provenance(self.fixture, evaluation, lineage)
        self.assertTrue(lineage.accepted)
        self.assertTrue(provenance.accepted)
        self.assertEqual(len(lineage.nodes), 37)
        self.assertEqual(len(provenance.nodes), 38)
        self.assertTrue(all(parent and child for parent, child, _ in lineage.edges))
        self.assertTrue(all(item.address.startswith("sha256:") for item in provenance.nodes))

    def test_policy_reconciliation_and_review_are_explicit(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        policy = default_causal_alpha_frontier_policy()
        decisions = policy.decide(evaluation)
        review = build_causal_alpha_frontier_review_queue(self.fixture, evaluation, decisions)
        reconciliation = reconcile_causal_alpha_frontier(self.fixture, evaluation, decisions)
        self.assertTrue(policy.accepted)
        self.assertEqual(len(decisions), 16)
        self.assertTrue(review.accepted)
        self.assertEqual(len(review.items), 13)
        self.assertEqual(len(review.blocking_items), 4)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.matched_count, 16)
        self.assertEqual(reconciliation.disposition_counts["quarantine"], 4)

    def test_scenario_and_validation_matrices_cover_all_rows(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        contracts = build_causal_alpha_frontier_contracts()
        metrics = build_causal_alpha_frontier_metrics(self.fixture, evaluation)
        scenarios = build_causal_alpha_frontier_scenario_matrix(self.fixture, evaluation)
        validation = build_causal_alpha_frontier_validation_matrix(self.fixture.fixture_id, evaluation, contracts, metrics)
        self.assertTrue(scenarios.accepted)
        self.assertTrue(validation.accepted)
        self.assertEqual(len(scenarios.scenarios), 16)
        self.assertEqual(len(validation.cells), 4)
        self.assertEqual(validation.for_capability("GNC-D11-C09").accepted_count, 4)
        self.assertEqual(len(scenarios.for_operation("negative_evidence")), 4)

    def test_runtime_closes_all_planes(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-test-runtime")
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.stage_count, 31)
        self.assertEqual(runtime.stage_ids[0], "data-audit")
        self.assertEqual(runtime.stage_ids[-1], "runbook")
        self.assertEqual(runtime.observability.completed_count, 31)
        self.assertEqual(runtime.observability.failed_count, 0)
        self.assertEqual(runtime.release.state.value, "ready")
        self.assertTrue(runtime.release.accepted)
        self.assertTrue(runtime.assurance.accepted)
        self.assertTrue(runtime.runbook.accepted)
        self.assertTrue(runbook_is_executable(runtime.runbook))

    def test_runtime_operational_counts_are_stable(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-operational")
        self.assertEqual(runtime.operational.allowed_count, 3)
        self.assertEqual(runtime.operational.review_count, 9)
        self.assertEqual(runtime.operational.quarantine_count, 4)
        self.assertEqual(len(runtime.artifacts.artifacts), 19)
        self.assertEqual(len(runtime.exports.envelopes), 10)
        self.assertEqual(len(runtime.review_view.rows), 16)
        self.assertTrue(runtime.boundary.accepted)
        self.assertEqual(runtime.boundary.excluded_claims[-1], "patient care")

    def test_integrity_and_depth_are_accepted(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-integrity")
        self.assertTrue(runtime.integrity.accepted)
        self.assertEqual(runtime.integrity.failed_checks, ())
        self.assertTrue(runtime.depth.accepted)
        self.assertEqual(runtime.depth.failed_checks, ())
        self.assertEqual(len(runtime.depth.implementation_modules), 10)
        self.assertEqual(len(runtime.depth.test_modules), 5)

    def test_quality_gate_and_assurance_have_no_failures(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-quality")
        self.assertTrue(runtime.quality.accepted)
        self.assertEqual(runtime.quality.failed_checks, ())
        self.assertTrue(runtime.assurance.accepted)
        self.assertEqual(runtime.assurance.checks[-1]["check_id"], "artifacts")
        self.assertEqual(len(runtime.assurance.limitations), 4)

    def test_replay_is_deterministic(self) -> None:
        receipt = replay_causal_alpha_frontier(self.fixture, replay_id="alpha-replay")
        self.assertTrue(receipt.accepted)
        self.assertTrue(receipt.deterministic)
        self.assertEqual(len(receipt.result_addresses), 16)
        self.assertEqual(receipt.first_address, receipt.second_address)

    def test_query_filters_by_operation_state_and_disposition(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-query")
        supported = query_causal_alpha_frontier(runtime.bundle, state="supported")
        quarantine = query_causal_alpha_frontier(runtime.bundle, disposition="quarantine")
        negative = query_causal_alpha_frontier(runtime.bundle, operation="negative_evidence")
        self.assertTrue(supported.accepted)
        self.assertEqual(len(supported.rows), 3)
        self.assertEqual(len(quarantine.rows), 4)
        self.assertEqual(len(negative.rows), 4)
        self.assertEqual(set(item["operation"] for item in negative.rows), {CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE})

    def test_review_view_is_stable_and_renderable(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-view")
        view = build_causal_alpha_frontier_review_view(self.fixture, runtime.evaluation, runtime.decisions, runtime.reconciliation, runtime.review)
        self.assertTrue(view.accepted)
        self.assertEqual(view.rows[0].record_id, "D11-C09-P")
        self.assertIn("| Record | Operation |", view.to_markdown())
        self.assertEqual(view.content_address, runtime.review_view.content_address)

    def test_release_bundle_and_artifacts_retain_addresses(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-bundle")
        self.assertTrue(runtime.bundle.publishable)
        self.assertEqual(runtime.artifacts.required_count, runtime.artifacts.resolved_count)
        self.assertEqual(runtime.artifacts.missing_artifact_ids, ())
        self.assertTrue(all(item.relative_path.endswith(".json") for item in runtime.artifacts.artifacts))

    def test_runbook_has_twelve_ordered_steps(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-runbook")
        self.assertEqual(len(runtime.runbook.steps), 12)
        self.assertEqual(tuple(item.sequence for item in runtime.runbook.steps), tuple(range(1, 13)))
        self.assertEqual(len(runtime.runbook.blocking_steps), 9)
        self.assertIn("causal-alpha-frontier-runtime", runtime.runbook.to_markdown())

    def test_foreign_rows_are_quarantined_in_every_operation(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-foreign")
        foreign = [row for row in runtime.review_view.rows if row.context_key == CAUSAL_ALPHA_FRONTIER_FOREIGN_CONTEXT_KEY]
        self.assertEqual(len(foreign), 4)
        self.assertTrue(all(row.observed_state == "out_of_domain" for row in foreign))
        self.assertTrue(all(row.disposition == "quarantine" for row in foreign))


if __name__ == "__main__":
    unittest.main()
