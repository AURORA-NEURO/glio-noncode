from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.errors import ValidationError
from glio_noncode.topology_frontier_contracts import default_topology_frontier_contracts
from glio_noncode.topology_frontier_exports import (
    export_topology_frontier_json,
    topology_frontier_export_receipt,
)
from glio_noncode.topology_frontier_fixture_eval import evaluate_topology_frontier_fixture
from glio_noncode.topology_frontier_lineage import (
    build_topology_frontier_lineage,
    verify_topology_frontier_lineage,
)
from glio_noncode.topology_frontier_observability import (
    build_topology_frontier_trace,
    compare_topology_frontier_runs,
)
from glio_noncode.topology_frontier_policy import (
    default_topology_frontier_policy_rules,
    evaluate_topology_frontier_policy,
)
from glio_noncode.topology_frontier_public_data import (
    TOPOLOGY_FRONTIER_CONTEXT_KEY,
    TopologyFrontierOperation,
    TopologyFrontierRole,
    audit_topology_frontier_data,
    default_topology_frontier_fixture,
)
from glio_noncode.topology_frontier_quality_gate import run_topology_frontier_quality_gate
from glio_noncode.topology_frontier_reconciliation import reconcile_topology_frontier
from glio_noncode.topology_frontier_release import build_topology_frontier_release
from glio_noncode.topology_frontier_replay import replay_topology_frontier_evaluation
from glio_noncode.topology_frontier_runtime import (
    TopologyFrontierRuntimeOptions,
    run_topology_frontier_pipeline,
)
from glio_noncode.topology_frontier_scenario_matrix import evaluate_topology_frontier_scenarios
from glio_noncode.topology_frontier_schema import (
    default_topology_frontier_schemas,
    validate_topology_frontier_schema,
)
from glio_noncode.topology_frontier_views import (
    build_topology_frontier_view,
    filter_topology_frontier_review_queue,
)


class TopologyFrontierContractMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_frontier_fixture()
        self.evaluation = evaluate_topology_frontier_fixture(self.fixture)
        self.quality = run_topology_frontier_quality_gate(self.fixture)
        self.view = build_topology_frontier_view(self.fixture, self.evaluation)

    def test_contract_registry_covers_four_operations(self) -> None:
        registry = default_topology_frontier_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual({item.operation for item in registry.contracts}, set(TopologyFrontierOperation))

    def test_contract_ids_are_unique_and_addressed(self) -> None:
        registry = default_topology_frontier_contracts()
        self.assertEqual(len({item.contract_id for item in registry.contracts}), 4)
        self.assertTrue(all(item.contract_id.startswith("GNC-D09-") for item in registry.contracts))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in registry.contracts))

    def test_contract_manifest_is_json_ready(self) -> None:
        import json

        payload = json.loads(export_topology_frontier_json(default_topology_frontier_contracts().manifest()))
        self.assertEqual(len(payload["contracts"]), 4)
        self.assertTrue(payload["content_address"].startswith("sha256:"))

    def test_contract_required_fields_are_non_empty(self) -> None:
        for contract in default_topology_frontier_contracts().contracts:
            self.assertTrue(contract.required_payload_fields)
            self.assertTrue(all(contract.required_payload_fields))
            self.assertTrue(contract.positive_states)
            self.assertTrue(contract.control_states)
            self.assertTrue(contract.issue_vocabulary)
            self.assertTrue(contract.prohibited_claims)

    def test_contract_control_states_exclude_supported(self) -> None:
        for contract in default_topology_frontier_contracts().contracts:
            self.assertNotIn("supported", contract.control_states)
            self.assertIn("partial", contract.control_states)
            self.assertIn("out_of_domain", contract.control_states)
            self.assertIn("invalid", contract.control_states)

    def test_each_operation_has_four_fixture_records(self) -> None:
        for operation in TopologyFrontierOperation:
            self.assertEqual(sum(item.operation is operation for item in self.fixture.records), 4)
            self.assertEqual(sum(item.operation is operation for item in self.evaluation.receipts), 4)

    def test_every_record_source_resolves(self) -> None:
        source_ids = set(self.fixture.source_map())
        self.assertTrue(all(set(item.source_ids) <= source_ids for item in self.fixture.records))
        self.assertTrue(all(item.source_ids for item in self.fixture.records))

    def test_every_record_has_exact_context_declaration(self) -> None:
        self.assertTrue(all(item.context_key == TOPOLOGY_FRONTIER_CONTEXT_KEY for item in self.fixture.records))
        self.assertTrue(all(item.context_key == self.evaluation.context_key for item in self.evaluation.receipts))

    def test_input_rows_are_serialized_lists(self) -> None:
        import json

        for record in self.fixture.records:
            self.assertIsInstance(json.loads(record.payload["input_text"]), list)

    def test_positive_and_control_role_order_is_stable(self) -> None:
        self.assertEqual(tuple(item.record_id for item in self.fixture.records[::4]), ("C13-POS-001", "C14-POS-001", "C15-POS-001", "C16-POS-001"))
        self.assertTrue(all(self.fixture.records[index].role is TopologyFrontierRole.POSITIVE for index in (0, 4, 8, 12)))

    def test_data_audit_rejects_changed_boundary(self) -> None:
        with self.assertRaises(ValidationError):
            replace(self.fixture, evidence_boundary="private_record")

    def test_data_audit_rejects_subject_key(self) -> None:
        record = replace(self.fixture.records[0], payload={**self.fixture.records[0].payload, "subject": "not-allowed"})
        altered = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        report = audit_topology_frontier_data(altered)
        self.assertFalse(report.accepted)
        self.assertIn("no-subject-identifiers", report.failed_check_ids)

    def test_evaluation_has_seven_checks_per_record_and_eight_global(self) -> None:
        self.assertEqual(len(self.evaluation.checks), 16 * 7 + 8)
        self.assertEqual(sum(item.record_id is None for item in self.evaluation.checks), 8)

    def test_evaluation_issue_floor_is_local_to_record(self) -> None:
        record = replace(self.fixture.records[0], expected_state="partial")
        altered = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        report = evaluate_topology_frontier_fixture(altered)
        self.assertFalse(report.accepted)
        self.assertIn("C13-POS-001:expected-state", report.failed_check_ids)

    def test_evaluation_retains_invalid_ecDNA_control(self) -> None:
        receipt = self.evaluation.receipts[3]
        self.assertEqual(receipt.adapter_state, "invalid")
        self.assertIn("invalid_ecdna_record", receipt.observed_issue_codes)
        self.assertEqual(receipt.primary_count, 0)

    def test_evaluation_retains_invalid_compartment_control(self) -> None:
        receipt = self.evaluation.receipts[7]
        self.assertEqual(receipt.adapter_state, "invalid")
        self.assertIn("invalid_compartment_record", receipt.observed_issue_codes)

    def test_evaluation_retains_exact_context_mismatch(self) -> None:
        for record_id in ("C13-CTRL-002", "C14-CTRL-002", "C15-CTRL-003", "C16-CTRL-001"):
            receipt = next(item for item in self.evaluation.receipts if item.record_id == record_id)
            self.assertEqual(receipt.adapter_state, "out_of_domain")
            self.assertIn("context_mismatch", receipt.observed_issue_codes)

    def test_replay_has_eight_checks(self) -> None:
        report = replay_topology_frontier_evaluation(self.evaluation, fixture=self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 8)
        self.assertEqual(report.failed_check_ids, ())

    def test_replay_detects_state_change(self) -> None:
        altered = replace(self.evaluation.receipts[0], adapter_state="partial")
        evaluation = replace(self.evaluation, receipts=(altered, *self.evaluation.receipts[1:]))
        report = replay_topology_frontier_evaluation(evaluation, fixture=self.fixture)
        self.assertFalse(report.accepted)
        self.assertIn("state-replay", report.failed_check_ids)

    def test_replay_detects_receipt_address_change(self) -> None:
        altered = replace(self.evaluation.receipts[0], content_address="sha256:changed")
        evaluation = replace(self.evaluation, receipts=(altered, *self.evaluation.receipts[1:]))
        report = replay_topology_frontier_evaluation(evaluation, fixture=self.fixture)
        self.assertFalse(report.accepted)
        self.assertIn("receipt-address-replay", report.failed_check_ids)

    def test_scenarios_have_three_checks_per_record(self) -> None:
        report = evaluate_topology_frontier_scenarios(self.evaluation, fixture=self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 48)
        self.assertEqual(len(report.scenarios), 16)

    def test_scenarios_reject_positive_control_role_drift(self) -> None:
        record = replace(self.fixture.records[0], role=TopologyFrontierRole.CONTROL)
        altered_fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        report = evaluate_topology_frontier_scenarios(self.evaluation, fixture=altered_fixture)
        self.assertFalse(report.accepted)
        self.assertIn("C13-POS-001:role", report.failed_check_ids)

    def test_policy_has_eight_rules_and_fourteen_checks(self) -> None:
        rules = default_topology_frontier_policy_rules()
        report = evaluate_topology_frontier_policy(self.fixture, self.evaluation, rules=rules)
        self.assertTrue(report.accepted)
        self.assertEqual(len(rules), 8)
        self.assertEqual(len(report.checks), 14)

    def test_policy_rejects_wrong_context(self) -> None:
        altered = replace(self.fixture, context_key="GRCh38|glioma|adult|differentiated|tumor|unknown")
        report = evaluate_topology_frontier_policy(altered, self.evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("context", report.failed_check_ids)

    def test_schema_has_five_checks_per_operation(self) -> None:
        schemas = default_topology_frontier_schemas()
        report = validate_topology_frontier_schema(self.evaluation, schemas=schemas)
        self.assertTrue(report.accepted)
        self.assertEqual(len(schemas), 4)
        self.assertEqual(len(report.checks), 20)

    def test_schema_rejects_unknown_state(self) -> None:
        altered = replace(self.evaluation.receipts[0], adapter_state="unknown")
        evaluation = replace(self.evaluation, receipts=(altered, *self.evaluation.receipts[1:]))
        report = validate_topology_frontier_schema(evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("ecdna_regulatory_contact:state-values", report.failed_check_ids)

    def test_lineage_has_one_edge_per_receipt(self) -> None:
        lineage = build_topology_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertEqual(len(lineage.edges), 16)
        self.assertEqual(tuple(item.record_id for item in lineage.edges), tuple(item.record_id for item in self.evaluation.receipts))

    def test_lineage_edges_have_sources_and_addresses(self) -> None:
        lineage = build_topology_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(all(item.source_ids for item in lineage.edges))
        self.assertTrue(all(item.output_address.startswith("sha256:") for item in lineage.edges))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in lineage.edges))

    def test_lineage_rejects_missing_source_set(self) -> None:
        lineage = build_topology_frontier_lineage(self.fixture, self.evaluation)
        altered = replace(lineage, source_ids=tuple(lineage.source_ids[:-1]))
        self.assertIn("source-closure", verify_topology_frontier_lineage(altered, self.fixture, self.evaluation))

    def test_lineage_rejects_changed_output_state(self) -> None:
        lineage = build_topology_frontier_lineage(self.fixture, self.evaluation)
        altered_edge = replace(lineage.edges[0], output_state="partial")
        altered = replace(lineage, edges=(altered_edge, *lineage.edges[1:]))
        failures = verify_topology_frontier_lineage(altered, self.fixture, self.evaluation)
        self.assertIn("receipt-match:C13-POS-001", failures)

    def test_reconciliation_has_three_global_checks(self) -> None:
        report = reconcile_topology_frontier(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.items), 16)
        self.assertEqual(len(report.global_checks), 3)
        self.assertEqual(report.failed_check_ids, ())

    def test_reconciliation_detects_expected_state_drift(self) -> None:
        record = replace(self.fixture.records[0], expected_state="partial")
        altered_fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        report = reconcile_topology_frontier(altered_fixture, self.evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("C13-POS-001:reconciliation", report.failed_check_ids)

    def test_quality_gate_has_expected_check_identifiers(self) -> None:
        self.assertEqual(
            tuple(item.check_id for item in self.quality.checks),
            ("data-audit", "evaluation", "replay", "scenarios", "policy", "schema", "lineage", "reconciliation", "record-closure", "source-closure", "operation-closure", "bundle"),
        )

    def test_quality_gate_rejects_changed_fixture_context(self) -> None:
        altered = replace(self.fixture, context_key="GRCh38|glioma|pediatric|stem_like|tumor|unknown")
        report = run_topology_frontier_quality_gate(altered)
        self.assertFalse(report.accepted)
        self.assertIn("data-audit", report.failed_check_ids)
        self.assertIn("evaluation", report.failed_check_ids)

    def test_bundle_record_and_source_closure(self) -> None:
        bundle = self.quality.bundle
        self.assertEqual(len(bundle.record_ids), 16)
        self.assertEqual(len(bundle.source_ids), 5)
        self.assertEqual(set(bundle.record_ids), {item.record_id for item in self.evaluation.receipts})
        self.assertEqual(set(bundle.source_ids), set(self.fixture.source_map()))
        self.assertTrue(bundle.bundle_address.startswith("sha256:"))

    def test_bundle_metrics_match_evaluation(self) -> None:
        metrics = self.quality.bundle.metrics
        self.assertEqual(metrics.total_records, len(self.evaluation.receipts))
        self.assertEqual(metrics.total_positive, self.evaluation.positive_count)
        self.assertEqual(metrics.total_controls, self.evaluation.control_count)

    def test_runtime_is_accepted(self) -> None:
        runtime = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="matrix"), fixture=self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.status, "accepted")
        self.assertEqual(runtime.fixture_id, self.fixture.fixture_id)

    def test_runtime_trace_has_monotonic_sequences(self) -> None:
        runtime = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="matrix-trace"), fixture=self.fixture)
        trace = build_topology_frontier_trace(runtime)
        self.assertEqual(tuple(item.sequence for item in trace.events), tuple(range(1, 10)))
        self.assertEqual(tuple(item.stage for item in trace.events), tuple(item.stage for item in trace.stage_receipts))

    def test_runtime_comparison_has_no_state_changes(self) -> None:
        left = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="left"), fixture=self.fixture)
        right = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="right"), fixture=self.fixture)
        comparison = compare_topology_frontier_runs(left, right)
        self.assertTrue(comparison.equivalent)
        self.assertEqual(comparison.state_changes, ())

    def test_runtime_comparison_detects_state_change(self) -> None:
        left = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id="left"), fixture=self.fixture)
        altered_receipts = (
            replace(left.quality.bundle.evaluation.receipts[0], adapter_state="partial"),
            *left.quality.bundle.evaluation.receipts[1:],
        )
        altered_evaluation = replace(left.quality.bundle.evaluation, receipts=altered_receipts)
        altered_bundle = replace(left.quality.bundle, evaluation=altered_evaluation)
        altered_quality = replace(left.quality, bundle=altered_bundle)
        right = replace(left, run_id="right", status="rejected", quality=altered_quality)
        comparison = compare_topology_frontier_runs(left, right)
        self.assertFalse(comparison.equivalent)
        self.assertIn("C13-POS-001", {item[0] for item in comparison.state_changes})

    def test_release_requires_accepted_quality(self) -> None:
        failed_check = replace(self.quality.checks[0], passed=False)
        rejected = replace(self.quality, checks=(failed_check, *self.quality.checks[1:]))
        with self.assertRaises(ValidationError):
            build_topology_frontier_release(rejected, run_id="rejected", release_id="rejected")

    def test_review_queue_contains_only_non_supported_states(self) -> None:
        self.assertTrue(all(item.state != "supported" for item in self.view.review_queue))
        self.assertEqual(len(filter_topology_frontier_review_queue(self.view, states=("partial",))), 6)
        self.assertEqual(len(filter_topology_frontier_review_queue(self.view, maximum_priority=2)), 6)

    def test_review_queue_can_filter_operation(self) -> None:
        rows = filter_topology_frontier_review_queue(self.view, operations=(TopologyFrontierOperation.ECDNA_CONTACT,))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(item.operation is TopologyFrontierOperation.ECDNA_CONTACT for item in rows))

    def test_export_receipt_is_addressed(self) -> None:
        payload = export_topology_frontier_json(self.quality.bundle)
        receipt = topology_frontier_export_receipt("bundle.json", payload)
        self.assertEqual(receipt["export_name"], "bundle.json")
        self.assertGreater(receipt["byte_count"], 100)
        self.assertTrue(receipt["content_address"].startswith("sha256:"))

    def test_all_content_addresses_have_expected_prefix(self) -> None:
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))
        self.assertTrue(self.evaluation.content_address.startswith("sha256:"))
        self.assertTrue(self.quality.content_address.startswith("sha256:"))
        self.assertTrue(self.view.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
