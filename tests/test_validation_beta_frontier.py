"""Deep contract tests for Domain 13 validation-beta C05-C12."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.validation_beta_frontier_adapters import (
    default_validation_beta_frontier_adapters,
    validate_validation_beta_frontier_payload as validate_adapter_payload,
)
from glio_noncode.validation_beta_frontier_artifacts import build_validation_beta_frontier_artifact_inventory
from glio_noncode.validation_beta_frontier_checks import run_validation_beta_frontier_invariants
from glio_noncode.validation_beta_frontier_claim_boundary import build_validation_beta_frontier_claim_boundary
from glio_noncode.validation_beta_frontier_contracts import default_validation_beta_frontier_contracts, validate_validation_beta_frontier_payload as validate_contract_payload
from glio_noncode.validation_beta_frontier_control_coverage import (
    build_validation_beta_frontier_control_coverage,
    validation_beta_frontier_controls_are_balanced,
)
from glio_noncode.validation_beta_frontier_depth import audit_validation_beta_frontier_depth
from glio_noncode.validation_beta_frontier_exports import (
    export_validation_beta_frontier_json,
    export_validation_beta_frontier_review_csv,
    render_validation_beta_frontier_markdown,
)
from glio_noncode.validation_beta_frontier_failure_injection import run_validation_beta_frontier_failure_injections
from glio_noncode.validation_beta_frontier_fixture_eval import evaluate_validation_beta_frontier_fixture
from glio_noncode.validation_beta_frontier_fixture_manifest import build_validation_beta_frontier_fixture_manifest
from glio_noncode.validation_beta_frontier_governance import (
    assemble_validation_beta_frontier_bundle,
    build_validation_beta_frontier_claim_boundary as build_claim_boundary,
    build_validation_beta_frontier_lineage,
    build_validation_beta_frontier_operational_matrix,
    build_validation_beta_frontier_release_manifest,
    build_validation_beta_frontier_review_queue,
    build_validation_beta_frontier_runbook,
    build_validation_beta_frontier_scenario_matrix,
    build_validation_beta_frontier_source_registry,
    evaluate_validation_beta_frontier_integrity,
    evaluate_validation_beta_frontier_quality,
    materialize_validation_beta_frontier_policy,
    measure_validation_beta_frontier,
    reconcile_validation_beta_frontier,
    replay_validation_beta_frontier,
)
from glio_noncode.validation_beta_frontier_integrity import validation_beta_frontier_integrity_is_closed
from glio_noncode.validation_beta_frontier_operation_catalog import default_validation_beta_frontier_operation_catalog
from glio_noncode.validation_beta_frontier_parameter_receipt import build_validation_beta_frontier_parameter_receipt
from glio_noncode.validation_beta_frontier_package import build_validation_beta_frontier_package_manifest
from glio_noncode.validation_beta_frontier_policy import validation_beta_frontier_policy_summary
from glio_noncode.validation_beta_frontier_public_data import (
    VALIDATION_BETA_FRONTIER_CONTEXT_KEY,
    ValidationBetaFrontierOperation,
    audit_validation_beta_frontier_data,
    default_validation_beta_frontier_fixture,
    validation_beta_frontier_fixture_json,
)
from glio_noncode.validation_beta_frontier_query import query_validation_beta_frontier
from glio_noncode.validation_beta_frontier_reconciliation import validation_beta_frontier_reconciliation_summary
from glio_noncode.validation_beta_frontier_recovery import build_validation_beta_frontier_recovery_plan
from glio_noncode.validation_beta_frontier_release import validation_beta_frontier_release_ready
from glio_noncode.validation_beta_frontier_review_queue import (
    filter_validation_beta_frontier_review_queue,
    validation_beta_frontier_review_summary,
)
from glio_noncode.validation_beta_frontier_runtime import run_validation_beta_frontier_runtime
from glio_noncode.validation_beta_frontier_schema import (
    default_validation_beta_frontier_schema,
    validate_validation_beta_frontier_output,
)
from glio_noncode.validation_beta_frontier_state_distribution import validation_beta_frontier_state_distribution
from glio_noncode.validation_beta_frontier_summary import build_validation_beta_frontier_summary
from glio_noncode.validation_beta_frontier_transcript import render_validation_beta_frontier_transcript
from glio_noncode.validation_beta_frontier_views import build_validation_beta_frontier_review_view


class ValidationBetaFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_validation_beta_frontier_fixture()
        cls.evaluation = evaluate_validation_beta_frontier_fixture(cls.fixture)
        cls.contracts = default_validation_beta_frontier_contracts()
        cls.schema = default_validation_beta_frontier_schema()
        cls.metrics = measure_validation_beta_frontier(cls.evaluation)
        cls.lineage = build_validation_beta_frontier_lineage(cls.fixture, cls.evaluation)
        cls.policy = materialize_validation_beta_frontier_policy(cls.evaluation)
        cls.reconciliation = reconcile_validation_beta_frontier(cls.fixture, cls.evaluation)
        cls.quality = evaluate_validation_beta_frontier_quality(cls.fixture, cls.evaluation, cls.contracts, cls.schema, cls.lineage, cls.reconciliation)
        cls.replay = replay_validation_beta_frontier(cls.fixture)
        cls.release = build_validation_beta_frontier_release_manifest(cls.quality, cls.replay, cls.policy)

    def test_fixture_has_public_sources_and_balanced_records(self) -> None:
        audit = audit_validation_beta_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(self.fixture.sources), 7)
        self.assertEqual(len(self.fixture.records), 32)
        self.assertEqual(len(self.fixture.positive_records), 8)
        self.assertEqual(len(self.fixture.control_records), 24)
        self.assertEqual(self.fixture.context_key, VALIDATION_BETA_FRONTIER_CONTEXT_KEY)
        self.assertEqual({record.operation for record in self.fixture.records}, set(ValidationBetaFrontierOperation))

    def test_fixture_source_receipts_are_https_and_addressed(self) -> None:
        self.assertTrue(all(source.uri.startswith("https://") for source in self.fixture.sources))
        self.assertTrue(all(source.content_address.startswith("sha256:") for source in self.fixture.sources))
        self.assertTrue(all(record.content_address.startswith("sha256:") for record in self.fixture.records))
        self.assertTrue(all(set(record.source_ids).issubset(self.fixture.source_map()) for record in self.fixture.records))

    def test_all_rows_execute_against_expected_states(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.rows), 32)
        self.assertEqual(self.evaluation.positive_count, 8)
        self.assertEqual(self.evaluation.control_count, 24)
        self.assertEqual(self.evaluation.mismatch_count, 0)

    def test_state_distribution_retains_positive_and_controls(self) -> None:
        distribution = validation_beta_frontier_state_distribution(self.evaluation)
        self.assertEqual(distribution["ready_for_review"], 8)
        self.assertEqual(distribution["blocked"], 16)
        self.assertEqual(distribution["out_of_domain"], 2)
        self.assertEqual(distribution["partial"], 3)
        self.assertEqual(distribution["abstained"], 3)

    def test_each_operation_has_one_positive_and_three_controls(self) -> None:
        for operation in ValidationBetaFrontierOperation:
            rows = self.evaluation.by_operation(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(row.record_id.endswith("POS-001") for row in rows), 1)
            self.assertEqual(sum("CTRL" in row.record_id for row in rows), 3)
            self.assertTrue(all(row.accepted for row in rows))

    def test_crispr_paths_include_both_modes(self) -> None:
        row = self.evaluation.by_operation(ValidationBetaFrontierOperation.CRISPR_DESIGN)[0]
        self.assertEqual(set(row.result["modes"]), {"crispri", "crispra"})
        self.assertTrue(all(row.result["modes"][mode]["guides"] for mode in ("crispri", "crispra")))

    def test_base_editing_retains_edit_payload(self) -> None:
        row = self.evaluation.by_operation(ValidationBetaFrontierOperation.BASE_EDITING)[0]
        package = row.result["modes"]["base_editing"]
        self.assertTrue(package["guides"])
        self.assertTrue(any(item.get("edit_payload") == "C>T" for item in package["guides"]))

    def test_prime_editing_retains_pbs_rtt_and_flank_blocker(self) -> None:
        positive = self.evaluation.by_operation(ValidationBetaFrontierOperation.PRIME_EDITING)[0]
        guides = positive.result["modes"]["prime_editing"]["guides"]
        self.assertTrue(guides)
        self.assertTrue(all(item["pbs_sequence"] and item["rtt_sequence"] for item in guides))
        blocker = self.evaluation.by_operation(ValidationBetaFrontierOperation.PRIME_EDITING)[2]
        self.assertIn("prime_editing_flank_shortage", blocker.observed_issue_codes)

    def test_reporter_keeps_reference_alternate_pair(self) -> None:
        row = self.evaluation.by_operation(ValidationBetaFrontierOperation.ALLELE_REPORTER)[0]
        constructs = row.result["modes"]["allele_specific_reporter"]["constructs"]
        self.assertEqual({item["allele"] for item in constructs}, {"reference", "alternate"})
        self.assertEqual(len(constructs), 2)

    def test_model_eligibility_is_context_gated(self) -> None:
        positive = self.evaluation.by_operation(ValidationBetaFrontierOperation.MODEL_ELIGIBILITY)[0]
        self.assertEqual(positive.observed_state, "ready_for_review")
        self.assertTrue(positive.result["results"][0]["eligible"])
        foreign = self.evaluation.by_operation(ValidationBetaFrontierOperation.MODEL_ELIGIBILITY)[1]
        self.assertEqual(foreign.observed_state, "out_of_domain")
        self.assertIn("context_mismatch", foreign.observed_issue_codes)

    def test_guide_oligo_adapter_retains_valid_rows_and_quarantines_invalid(self) -> None:
        positive = self.evaluation.by_operation(ValidationBetaFrontierOperation.GUIDE_OLIGO)[0]
        self.assertEqual(len(positive.result["observations"]), 2)
        invalid = self.evaluation.by_operation(ValidationBetaFrontierOperation.GUIDE_OLIGO)[1]
        self.assertEqual(invalid.observed_state, "partial")
        self.assertIn("invalid_guide_oligo_row", invalid.observed_issue_codes)

    def test_controls_are_deterministic_and_balanced(self) -> None:
        positive = self.evaluation.by_operation(ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION)[0]
        self.assertEqual(len(positive.result["assignments"]), 18)
        self.assertEqual(len({item["assignment_id"] for item in positive.result["assignments"]}), 18)
        controls = build_validation_beta_frontier_control_coverage(self.evaluation)
        self.assertTrue(validation_beta_frontier_controls_are_balanced(controls))

    def test_power_estimate_exposes_shortfall_and_context_boundary(self) -> None:
        positive = self.evaluation.by_operation(ValidationBetaFrontierOperation.POWER_REPLICATION)[0]
        self.assertTrue(positive.result["results"])
        self.assertEqual(positive.observed_state, "ready_for_review")
        shortfall = self.evaluation.by_operation(ValidationBetaFrontierOperation.POWER_REPLICATION)[1]
        self.assertEqual(shortfall.observed_state, "partial")
        foreign = self.evaluation.by_operation(ValidationBetaFrontierOperation.POWER_REPLICATION)[2]
        self.assertEqual(foreign.observed_state, "out_of_domain")

    def test_contracts_cover_all_operations_and_reject_missing_input(self) -> None:
        self.assertEqual(len(self.contracts.contracts), 8)
        self.assertEqual({item.operation for item in self.contracts.contracts}, set(ValidationBetaFrontierOperation))
        result = validate_contract_payload(ValidationBetaFrontierOperation.POWER_REPLICATION, {})
        self.assertFalse(result["valid"])
        self.assertIn("observations", result["missing_fields"])
        adapters = default_validation_beta_frontier_adapters()
        self.assertEqual(len(adapters.specs), 8)
        self.assertTrue(validate_adapter_payload(ValidationBetaFrontierOperation.POWER_REPLICATION, {"observations": []}).accepted)

    def test_schema_is_closed_and_sensitive_input_is_not_output(self) -> None:
        self.assertTrue(self.schema.accepted)
        self.assertEqual(len(self.schema.operations), 8)
        output = validate_validation_beta_frontier_output(ValidationBetaFrontierOperation.GUIDE_OLIGO, {"state": "partial", "observations": [], "issues": [], "warnings": [], "content_address": "x"})
        self.assertTrue(output["valid"])
        self.assertEqual(output["sensitive_projection_fields"], ())

    def test_lineage_has_no_orphans(self) -> None:
        self.assertTrue(self.lineage.closed)
        self.assertFalse(self.lineage.orphan_ids)
        self.assertGreaterEqual(len(self.lineage.edges), 32)

    def test_policy_publishes_only_positive_review_ready_rows(self) -> None:
        self.assertEqual(self.policy.publish_count, 8)
        self.assertEqual(self.policy.review_count, 3)
        self.assertEqual(self.policy.quarantine_count, 21)
        self.assertTrue(all(item.record_id.endswith("POS-001") for item in self.policy.decisions if item.disposition == "publish"))
        self.assertTrue(all("clinical decision" in item.excluded_uses for item in self.policy.decisions))
        self.assertEqual(validation_beta_frontier_policy_summary(self.policy)["decision_count"], 32)

    def test_reconciliation_has_zero_mismatches(self) -> None:
        self.assertTrue(self.reconciliation.reconciled)
        self.assertFalse(self.reconciliation.mismatch_ids)
        self.assertEqual(validation_beta_frontier_reconciliation_summary(self.reconciliation)["item_count"], 32)

    def test_quality_gate_has_explicit_checks(self) -> None:
        self.assertTrue(self.quality.accepted)
        self.assertEqual(len(self.quality.checks), 12)
        self.assertFalse(self.quality.failed_check_ids)

    def test_replay_is_deterministic(self) -> None:
        self.assertTrue(self.replay.deterministic)
        self.assertEqual(self.replay.original_address, self.replay.replay_address)

    def test_review_queue_contains_non_publishable_rows(self) -> None:
        queue = build_validation_beta_frontier_review_queue(self.evaluation, self.policy)
        self.assertEqual(queue.open_count, 24)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(filter_validation_beta_frontier_review_queue(queue, minimum_priority=3)), 19)
        self.assertEqual(validation_beta_frontier_review_summary(queue)["open_count"], 24)

    def test_scenarios_keep_all_rows_and_dispositions(self) -> None:
        matrix = build_validation_beta_frontier_scenario_matrix(self.evaluation, self.policy)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.scenarios), 32)
        self.assertEqual({item.expected_disposition for item in matrix.scenarios}, {"publish", "review", "quarantine"})

    def test_depth_audit_is_substantive(self) -> None:
        depth = audit_validation_beta_frontier_depth(self.fixture, self.evaluation, self.metrics, self.lineage, self.quality)
        self.assertTrue(depth.accepted)
        self.assertEqual(len(depth.checks), 20)
        self.assertTrue(all(item.observed >= item.required for item in depth.checks))

    def test_artifacts_sources_and_integrity_are_closed(self) -> None:
        artifacts = build_validation_beta_frontier_artifact_inventory(self.fixture, self.evaluation)
        sources = build_validation_beta_frontier_source_registry(self.fixture)
        integrity = evaluate_validation_beta_frontier_integrity(self.fixture, self.evaluation)
        self.assertTrue(artifacts.closed)
        self.assertTrue(sources.closed)
        self.assertTrue(validation_beta_frontier_integrity_is_closed(integrity))
        self.assertEqual(len(artifacts.artifacts), 2)

    def test_release_bundle_and_recovery_are_ready(self) -> None:
        self.assertTrue(self.release.ready)
        self.assertEqual(len(self.release.publishable_records), 8)
        bundle = assemble_validation_beta_frontier_bundle(self.fixture, self.evaluation, self.lineage, self.policy, self.quality, self.release)
        self.assertTrue(bundle.publishable)
        self.assertTrue(validation_beta_frontier_release_ready(self.release))
        recovery = build_validation_beta_frontier_recovery_plan(self.policy, self.quality, self.release)
        self.assertTrue(recovery["executable"])

    def test_failure_probes_and_invariants_pass(self) -> None:
        failures = run_validation_beta_frontier_failure_injections(self.fixture)
        self.assertTrue(failures.accepted)
        self.assertGreaterEqual(len(failures.probes), 12)
        invariants = run_validation_beta_frontier_invariants(self.fixture, self.evaluation)
        self.assertTrue(invariants["accepted"])

    def test_query_and_views_preserve_state_fields(self) -> None:
        query = query_validation_beta_frontier(self.evaluation, operation=ValidationBetaFrontierOperation.PRIME_EDITING)
        self.assertEqual(len(query.rows), 4)
        self.assertEqual(len(query.record_ids), 4)
        view = build_validation_beta_frontier_review_view(self.evaluation)
        self.assertTrue(view.accepted)
        self.assertEqual(len(view.rows), 32)
        self.assertIn("issue_codes", view.visible_fields)

    def test_fixture_manifest_and_public_catalog_are_complete(self) -> None:
        manifest = build_validation_beta_frontier_fixture_manifest(self.fixture)
        self.assertEqual(manifest["record_count"], 32)
        catalog = default_validation_beta_frontier_operation_catalog()
        self.assertEqual(len(catalog), 8)
        self.assertEqual({item["capability_id"] for item in catalog}, {f"GNC-D13-C{index:02d}" for index in range(5, 13)})

    def test_claim_boundary_and_parameter_receipts_are_explicit(self) -> None:
        boundary = build_claim_boundary()
        self.assertTrue(boundary.accepted)
        self.assertIn("guide efficacy", boundary.excluded_claims)
        receipt = build_validation_beta_frontier_parameter_receipt(context_key=VALIDATION_BETA_FRONTIER_CONTEXT_KEY, run_id="test")
        self.assertEqual(receipt["context_key"], VALIDATION_BETA_FRONTIER_CONTEXT_KEY)
        self.assertTrue(receipt["content_address"])

    def test_text_exports_are_stable_and_sanitized(self) -> None:
        payload = export_validation_beta_frontier_json(self.evaluation)
        csv = export_validation_beta_frontier_review_csv(self.evaluation)
        markdown = render_validation_beta_frontier_markdown(self.evaluation)
        self.assertEqual(json.loads(payload)["accepted"], True)
        self.assertEqual(csv.splitlines()[0], "record_id,operation,expected_state,observed_state,accepted,issue_codes")
        self.assertIn("# Validation-beta frontier review", markdown)
        self.assertNotIn("patient", markdown.lower())

    def test_runtime_has_full_ordered_rehearsal(self) -> None:
        report = run_validation_beta_frontier_runtime()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.stages), 25)
        self.assertEqual(tuple(item.sequence for item in report.stages), tuple(range(1, 26)))
        self.assertEqual(report.stage_ids[-1], "observability")
        self.assertTrue(report.release.ready)
        self.assertTrue(report.bundle.publishable)
        transcript = render_validation_beta_frontier_transcript(report)
        self.assertIn("run=validation-beta-frontier-runtime", transcript)

    def test_fixture_json_is_round_tripable_shape(self) -> None:
        payload = json.loads(validation_beta_frontier_fixture_json(self.fixture))
        self.assertEqual(payload["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(len(payload["records"]), 32)

    def test_mutated_expected_state_is_detected(self) -> None:
        first = self.fixture.records[0]
        mutated = replace(first, expected_state="blocked")
        fixture = replace(self.fixture, records=(mutated,) + self.fixture.records[1:])
        evaluation = evaluate_validation_beta_frontier_fixture(fixture)
        self.assertFalse(evaluation.accepted)
        self.assertEqual(evaluation.mismatch_count, 1)

    def test_source_mutation_fails_data_audit(self) -> None:
        source = self.fixture.sources[0]
        with self.assertRaises(ValueError):
            replace(source, uri="http://invalid.example/source")


if __name__ == "__main__":
    unittest.main()
