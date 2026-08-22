from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.cell_state_frontier_contracts import default_cell_state_frontier_contracts
from glio_noncode.cell_state_frontier_fixture_eval import evaluate_cell_state_frontier_fixture
from glio_noncode.cell_state_frontier_lineage import (
    build_cell_state_frontier_lineage,
    verify_cell_state_frontier_lineage,
)
from glio_noncode.cell_state_frontier_metrics import compute_cell_state_frontier_metrics
from glio_noncode.cell_state_frontier_observability import compare_cell_state_frontier_runs
from glio_noncode.cell_state_frontier_policy import (
    default_cell_state_frontier_policy_rules,
    evaluate_cell_state_frontier_policy,
)
from glio_noncode.cell_state_frontier_public_data import (
    CELL_STATE_FRONTIER_CONTEXT_KEY,
    CellStateFrontierOperation,
    CellStateFrontierRole,
    audit_cell_state_frontier_data,
    default_cell_state_frontier_fixture,
)
from glio_noncode.cell_state_frontier_quality_gate import run_cell_state_frontier_quality_gate
from glio_noncode.cell_state_frontier_reconciliation import reconcile_cell_state_frontier
from glio_noncode.cell_state_frontier_release import build_cell_state_frontier_release
from glio_noncode.cell_state_frontier_replay import replay_cell_state_frontier_evaluation
from glio_noncode.cell_state_frontier_runtime import (
    CellStateFrontierRuntimeOptions,
    run_cell_state_frontier_pipeline,
)
from glio_noncode.cell_state_frontier_scenario_matrix import evaluate_cell_state_frontier_scenarios
from glio_noncode.cell_state_frontier_schema import (
    default_cell_state_frontier_schemas,
    validate_cell_state_frontier_schema,
)
from glio_noncode.cell_state_frontier_views import (
    build_cell_state_frontier_view,
    filter_cell_state_frontier_review_queue,
)


class CellStateFrontierContractMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_cell_state_frontier_fixture()
        self.evaluation = evaluate_cell_state_frontier_fixture(self.fixture)
        self.quality = run_cell_state_frontier_quality_gate(self.fixture)
        self.view = build_cell_state_frontier_view(self.fixture, self.evaluation)

    def test_contract_count_matches_operation_count(self) -> None:
        registry = default_cell_state_frontier_contracts()
        self.assertEqual(len(registry.contracts), len(tuple(CellStateFrontierOperation)))
        self.assertEqual({item.operation for item in registry.contracts}, set(CellStateFrontierOperation))

    def test_contract_ids_are_unique(self) -> None:
        registry = default_cell_state_frontier_contracts()
        ids = [item.contract_id for item in registry.contracts]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(item.startswith("GNC-D08-") for item in ids))

    def test_contract_addresses_are_unique(self) -> None:
        registry = default_cell_state_frontier_contracts()
        addresses = [item.content_address for item in registry.contracts]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(item.startswith("sha256:") for item in addresses))

    def test_contract_adapters_are_declared(self) -> None:
        registry = default_cell_state_frontier_contracts()
        names = {item.adapter_name for item in registry.contracts}
        self.assertEqual(names, {"CellStateAbundanceUncertaintyModel", "SingleCellReferenceMapper", "CellStateOODDetector", "CellStateContextPublisher"})

    def test_contract_positive_states_are_supported(self) -> None:
        registry = default_cell_state_frontier_contracts()
        self.assertTrue(all(item.positive_states == ("supported",) for item in registry.contracts))

    def test_contract_control_states_are_non_success_states(self) -> None:
        registry = default_cell_state_frontier_contracts()
        for contract in registry.contracts:
            self.assertNotIn("supported", contract.control_states)
            self.assertIn("partial", contract.control_states)
            self.assertIn("out_of_domain", contract.control_states)

    def test_contract_fields_include_raw_boundary_and_parameters(self) -> None:
        registry = default_cell_state_frontier_contracts()
        for contract in registry.contracts:
            self.assertIn("input_text", contract.required_payload_fields)
            self.assertTrue(contract.required_payload_fields)
            self.assertTrue(contract.issue_vocabulary)
            self.assertTrue(contract.prohibited_claims)

    def test_contract_manifest_is_json_serializable(self) -> None:
        manifest = default_cell_state_frontier_contracts().manifest()
        encoded = json.dumps(manifest, sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(len(decoded["contracts"]), 4)
        self.assertTrue(decoded["content_address"].startswith("sha256:"))

    def test_fixture_operations_are_ordered(self) -> None:
        self.assertEqual(
            tuple(item.operation for item in self.fixture.records[::4]),
            tuple(CellStateFrontierOperation),
        )

    def test_fixture_roles_are_ordered(self) -> None:
        self.assertTrue(all(self.fixture.records[index].role is CellStateFrontierRole.POSITIVE for index in (0, 4, 8, 12)))
        self.assertTrue(all(self.fixture.records[index].role is CellStateFrontierRole.CONTROL for index in (1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15)))

    def test_fixture_context_is_exact_for_record_metadata(self) -> None:
        self.assertTrue(all(item.context_key == CELL_STATE_FRONTIER_CONTEXT_KEY for item in self.fixture.records))
        self.assertTrue(all(item.context_key == self.evaluation.context_key for item in self.evaluation.receipts))

    def test_fixture_source_ids_are_non_empty(self) -> None:
        self.assertTrue(all(item.source_ids for item in self.fixture.records))
        self.assertTrue(all(item.source_id for item in self.fixture.sources))

    def test_fixture_payloads_have_serialized_rows(self) -> None:
        for record in self.fixture.records:
            self.assertIn("input_text", record.payload)
            self.assertIsInstance(record.payload["input_text"], str)
            self.assertIsInstance(json.loads(record.payload["input_text"]), list)

    def test_fixture_descriptions_are_distinct(self) -> None:
        descriptions = [item.description for item in self.fixture.records]
        self.assertEqual(len(descriptions), len(set(descriptions)))

    def test_audit_accepts_default_fixture(self) -> None:
        report = audit_cell_state_frontier_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_check_ids, ())

    def test_audit_rejects_missing_source(self) -> None:
        record = replace(self.fixture.records[0], source_ids=("not-a-source",))
        fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        report = audit_cell_state_frontier_data(fixture)
        self.assertFalse(report.accepted)
        self.assertIn("source-closure", report.failed_check_ids)

    def test_audit_rejects_wrong_context(self) -> None:
        fixture = replace(self.fixture, context_key="GRCh38|glioma|adult|differentiated|tumor|unknown")
        report = audit_cell_state_frontier_data(fixture)
        self.assertFalse(report.accepted)
        self.assertIn("fixture-context", report.failed_check_ids)

    def test_audit_rejects_subject_key_nested_in_payload(self) -> None:
        record = replace(self.fixture.records[0], payload=self.fixture.records[0].payload | {"nested": {"donor": "blocked"}})
        fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        report = audit_cell_state_frontier_data(fixture)
        self.assertFalse(report.accepted)
        self.assertIn("no-subject-identifiers", report.failed_check_ids)

    def test_evaluation_receipt_count_is_stable(self) -> None:
        self.assertEqual(len(self.evaluation.receipts), 16)
        self.assertEqual(len(self.evaluation.checks), 120)

    def test_evaluation_receipt_operations_are_complete(self) -> None:
        self.assertEqual({item.operation for item in self.evaluation.receipts}, set(CellStateFrontierOperation))

    def test_evaluation_receipt_roles_are_complete(self) -> None:
        self.assertEqual({item.role for item in self.evaluation.receipts}, {CellStateFrontierRole.POSITIVE, CellStateFrontierRole.CONTROL})

    def test_evaluation_primary_counts_are_nonnegative(self) -> None:
        self.assertTrue(all(item.primary_count >= 0 for item in self.evaluation.receipts))
        self.assertTrue(all(item.secondary_count >= 0 for item in self.evaluation.receipts))

    def test_evaluation_positive_summaries_are_clean(self) -> None:
        positives = [item for item in self.evaluation.receipts if item.role is CellStateFrontierRole.POSITIVE]
        self.assertTrue(all(item.summary["state"] == "supported" for item in positives))
        self.assertTrue(all("input_text" not in item.summary for item in positives))

    def test_evaluation_control_summaries_are_clean(self) -> None:
        controls = [item for item in self.evaluation.receipts if item.role is CellStateFrontierRole.CONTROL]
        self.assertTrue(all(item.summary["state"] != "supported" for item in controls))
        self.assertTrue(all("payload" not in item.summary for item in controls))

    def test_evaluation_issue_codes_match_record_floors(self) -> None:
        record_map = self.fixture.record_map()
        for receipt in self.evaluation.receipts:
            expected = set(record_map[receipt.record_id].expected_issue_codes)
            self.assertTrue(expected <= set(receipt.observed_issue_codes))

    def test_evaluation_addresses_are_prefixed(self) -> None:
        self.assertTrue(self.evaluation.catalog_address.startswith("sha256:"))
        self.assertTrue(self.evaluation.content_address.startswith("sha256:"))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.evaluation.receipts))

    def test_evaluation_failure_is_localized_to_drifted_record(self) -> None:
        record = replace(self.fixture.records[4], expected_state="partial")
        fixture = replace(self.fixture, records=(*self.fixture.records[:4], record, *self.fixture.records[5:]))
        report = evaluate_cell_state_frontier_fixture(fixture)
        self.assertFalse(report.accepted)
        self.assertIn("C14-POS-001:expected-state", report.failed_check_ids)

    def test_replay_accepts_default_evaluation(self) -> None:
        report = replay_cell_state_frontier_evaluation(self.evaluation, fixture=self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 8)

    def test_replay_addresses_are_present(self) -> None:
        report = replay_cell_state_frontier_evaluation(self.evaluation, fixture=self.fixture)
        self.assertTrue(report.content_address.startswith("sha256:"))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in report.checks))

    def test_replay_rejects_changed_receipt_state(self) -> None:
        altered = replace(self.evaluation.receipts[8], adapter_state="partial")
        evaluation = replace(self.evaluation, receipts=(*self.evaluation.receipts[:8], altered, *self.evaluation.receipts[9:]))
        report = replay_cell_state_frontier_evaluation(evaluation, fixture=self.fixture)
        self.assertFalse(report.accepted)
        self.assertIn("state-replay", report.failed_check_ids)

    def test_scenarios_cover_every_record(self) -> None:
        report = evaluate_cell_state_frontier_scenarios(self.evaluation)
        self.assertEqual(len(report.scenarios), 16)
        self.assertEqual(len(report.checks), 16)
        self.assertTrue(report.accepted)

    def test_scenarios_keep_expected_issue_floors(self) -> None:
        report = evaluate_cell_state_frontier_scenarios(self.evaluation)
        for scenario, check in zip(report.scenarios, report.checks, strict=True):
            self.assertEqual(scenario.scenario_id, check.scenario_id)
            self.assertTrue(check.passed)

    def test_policy_rule_ids_are_unique(self) -> None:
        rules = default_cell_state_frontier_policy_rules()
        self.assertEqual(len(rules), 12)
        self.assertEqual(len({item.rule_id for item in rules}), 12)

    def test_policy_rules_cover_all_operations(self) -> None:
        rules = default_cell_state_frontier_policy_rules()
        covered = {operation for rule in rules for operation in rule.applies_to}
        self.assertEqual(covered, set(CellStateFrontierOperation))

    def test_policy_rule_addresses_are_stable(self) -> None:
        first = default_cell_state_frontier_policy_rules()
        second = default_cell_state_frontier_policy_rules()
        self.assertEqual(tuple(item.content_address for item in first), tuple(item.content_address for item in second))

    def test_policy_passes_without_unknown_rules(self) -> None:
        report = evaluate_cell_state_frontier_policy(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_rule_ids, ())

    def test_policy_rejects_wrong_boundary(self) -> None:
        fixture = replace(self.fixture, context_key="GRCh38|glioma|adult|stem_like|normal|unknown")
        report = evaluate_cell_state_frontier_policy(fixture)
        self.assertFalse(report.accepted)
        self.assertIn("context-exact", report.failed_rule_ids)

    def test_schema_count_is_four(self) -> None:
        schemas = default_cell_state_frontier_schemas()
        self.assertEqual(len(schemas), 4)
        self.assertEqual({item.operation for item in schemas}, set(CellStateFrontierOperation))

    def test_schema_ids_are_unique(self) -> None:
        schemas = default_cell_state_frontier_schemas()
        self.assertEqual(len({item.schema_id for item in schemas}), 4)
        self.assertTrue(all(item.schema_id.startswith("GNC-D08-") for item in schemas))

    def test_schema_output_fields_are_unique(self) -> None:
        for schema in default_cell_state_frontier_schemas():
            names = schema.output_field_names
            self.assertEqual(len(names), len(set(names)), schema.schema_id)

    def test_schema_fields_are_non_empty(self) -> None:
        for schema in default_cell_state_frontier_schemas():
            self.assertTrue(schema.common_fields)
            self.assertTrue(schema.output_fields)
            self.assertTrue(all(item.name and item.value_type and item.description for item in schema.output_fields))

    def test_schema_accepts_default_evaluation(self) -> None:
        report = validate_cell_state_frontier_schema(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_check_ids, ())

    def test_schema_rejects_unknown_issue_code(self) -> None:
        altered = replace(self.evaluation.receipts[0], observed_issue_codes=("unknown-code",))
        evaluation = replace(self.evaluation, receipts=(altered, *self.evaluation.receipts[1:]))
        report = validate_cell_state_frontier_schema(self.fixture, evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("cell_state_abundance_interval:issues", report.failed_check_ids)

    def test_schema_rejects_claim_text(self) -> None:
        altered = replace(self.evaluation.receipts[4], summary=self.evaluation.receipts[4].summary | {"claim": "diagnostic"})
        evaluation = replace(self.evaluation, receipts=(*self.evaluation.receipts[:4], altered, *self.evaluation.receipts[5:]))
        report = validate_cell_state_frontier_schema(self.fixture, evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("single_cell_reference_mapping:claims", report.failed_check_ids)

    def test_metrics_have_four_operation_rows(self) -> None:
        metrics = compute_cell_state_frontier_metrics(self.evaluation)
        self.assertEqual(len(metrics.operation_metrics), 4)
        self.assertEqual(tuple(item.operation for item in metrics.operation_metrics), tuple(CellStateFrontierOperation))

    def test_metrics_record_conservation(self) -> None:
        metrics = compute_cell_state_frontier_metrics(self.evaluation)
        self.assertEqual(metrics.total_records, 16)
        self.assertEqual(metrics.positive_records + metrics.control_records, metrics.total_records)
        self.assertEqual(metrics.supported_records + metrics.review_records, metrics.total_records)

    def test_metrics_issue_count_matches_receipts(self) -> None:
        metrics = compute_cell_state_frontier_metrics(self.evaluation)
        expected = sum(bool(item.observed_issue_codes) for item in self.evaluation.receipts)
        self.assertEqual(metrics.issue_count, expected)

    def test_metrics_pass_rate_is_one_for_default(self) -> None:
        metrics = compute_cell_state_frontier_metrics(self.evaluation)
        self.assertEqual(metrics.check_pass_rate, 1.0)

    def test_view_operation_counts_conserve_fixture(self) -> None:
        self.assertEqual(sum(item.positive_count for item in self.view.operation_views), 4)
        self.assertEqual(sum(item.control_count for item in self.view.operation_views), 12)
        self.assertEqual(sum(item.review_count for item in self.view.operation_views), 12)

    def test_view_source_matrix_has_five_rows(self) -> None:
        self.assertEqual(len(self.view.source_matrix), 5)
        self.assertEqual({item.source_id for item in self.view.source_matrix}, set(self.fixture.source_map()))

    def test_view_review_queue_has_four_high_priority_rows(self) -> None:
        high = filter_cell_state_frontier_review_queue(self.view, maximum_priority=4)
        self.assertEqual(len(high), 12)
        self.assertEqual(sum(item.priority == 4 for item in high), 4)

    def test_view_operation_filter_is_exact(self) -> None:
        for operation in CellStateFrontierOperation:
            rows = filter_cell_state_frontier_review_queue(self.view, operations=(operation,))
            self.assertTrue(all(item.operation is operation for item in rows))
            self.assertEqual(len(rows), 3)

    def test_view_state_filter_is_exact(self) -> None:
        partial = filter_cell_state_frontier_review_queue(self.view, states=("partial",))
        out = filter_cell_state_frontier_review_queue(self.view, states=("out_of_domain",))
        self.assertEqual(len(partial), 8)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(item.state == "partial" for item in partial))
        self.assertTrue(all(item.state == "out_of_domain" for item in out))

    def test_lineage_has_one_edge_per_receipt(self) -> None:
        lineage = build_cell_state_frontier_lineage(self.fixture, self.evaluation)
        self.assertEqual(len(lineage.edges), len(self.evaluation.receipts))
        self.assertEqual(tuple(item.record_id for item in lineage.edges), tuple(item.record_id for item in self.evaluation.receipts))

    def test_lineage_edges_have_sources(self) -> None:
        lineage = build_cell_state_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(all(item.source_ids for item in lineage.edges))
        self.assertTrue(all(item.output_address.startswith("sha256:") for item in lineage.edges))

    def test_lineage_rejects_missing_source_set(self) -> None:
        lineage = build_cell_state_frontier_lineage(self.fixture, self.evaluation)
        altered = replace(lineage, source_ids=tuple(lineage.source_ids[:-1]))
        self.assertIn("source-closure", verify_cell_state_frontier_lineage(altered, self.fixture, self.evaluation))

    def test_reconciliation_has_three_global_checks(self) -> None:
        report = reconcile_cell_state_frontier(self.fixture, self.evaluation)
        self.assertEqual(len(report.checks), 3)
        self.assertTrue(all(passed for _, passed in report.checks))

    def test_reconciliation_issue_floors_are_sets(self) -> None:
        report = reconcile_cell_state_frontier(self.fixture, self.evaluation)
        for item in report.items:
            self.assertTrue(set(item.expected_issue_codes) <= set(item.observed_issue_codes))

    def test_reconciliation_failure_lists_record_id(self) -> None:
        record = replace(self.fixture.records[8], expected_state="partial")
        fixture = replace(self.fixture, records=(*self.fixture.records[:8], record, *self.fixture.records[9:]))
        evaluation = evaluate_cell_state_frontier_fixture(fixture)
        report = reconcile_cell_state_frontier(fixture, evaluation)
        self.assertIn("C15-POS-001", report.failed_record_ids)

    def test_quality_report_has_twelve_checks(self) -> None:
        self.assertEqual(len(self.quality.checks), 12)
        self.assertEqual(self.quality.failed_check_ids, ())

    def test_quality_component_addresses_are_present(self) -> None:
        bundle = self.quality.bundle
        values = (bundle.data_audit, bundle.evaluation, bundle.replay, bundle.scenarios, bundle.policy, bundle.lineage, bundle.reconciliation, bundle.metrics)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in values))

    def test_quality_bundle_contains_all_operations(self) -> None:
        operations = {item.operation for item in self.quality.bundle.evaluation.receipts}
        self.assertEqual(operations, set(CellStateFrontierOperation))

    def test_quality_rejects_wrong_expected_state(self) -> None:
        record = replace(self.fixture.records[12], expected_state="partial")
        fixture = replace(self.fixture, records=(*self.fixture.records[:12], record, *self.fixture.records[13:]))
        quality = run_cell_state_frontier_quality_gate(fixture)
        self.assertFalse(quality.accepted)
        self.assertIn("evaluation", quality.failed_check_ids)

    def test_runtime_default_run_is_accepted(self) -> None:
        runtime = run_cell_state_frontier_pipeline(fixture=self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.status, "accepted")

    def test_runtime_requested_exact_context_is_accepted(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="exact", requested_context_key=CELL_STATE_FRONTIER_CONTEXT_KEY), fixture=self.fixture)
        self.assertTrue(runtime.accepted)

    def test_runtime_requested_other_context_is_rejected(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="other", requested_context_key="GRCh38|glioma|adult|stem_like|normal|unknown"), fixture=self.fixture)
        self.assertFalse(runtime.accepted)
        self.assertEqual(runtime.status, "rejected")

    def test_runtime_strict_mode_is_rejected_by_review_count(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="strict", fail_on_review=True), fixture=self.fixture)
        self.assertFalse(runtime.accepted)
        self.assertGreater(runtime.quality.bundle.metrics.review_records, 0)

    def test_release_ready_matches_runtime_and_quality(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="ready"), fixture=self.fixture)
        release = build_cell_state_frontier_release(self.quality, runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(release.release_state, "ready")
        self.assertEqual(release.run_id, "ready")

    def test_release_blocked_matches_strict_runtime(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="blocked", fail_on_review=True), fixture=self.fixture)
        release = build_cell_state_frontier_release(self.quality, runtime)
        self.assertFalse(release.accepted)
        self.assertEqual(release.release_state, "blocked")

    def test_release_operation_ids_are_unique(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="release"), fixture=self.fixture)
        release = build_cell_state_frontier_release(self.quality, runtime)
        self.assertEqual(len(release.operation_ids), len(set(release.operation_ids)))
        self.assertEqual(set(release.operation_ids), {item.value for item in CellStateFrontierOperation})

    def test_runtime_trace_has_nine_events(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="trace"), fixture=self.fixture)
        from glio_noncode.cell_state_frontier_observability import build_cell_state_frontier_trace
        trace = build_cell_state_frontier_trace(runtime)
        self.assertEqual(len(trace.events), 9)
        self.assertEqual(tuple(item.sequence for item in trace.events), tuple(range(1, 10)))

    def test_runtime_trace_bundle_event_contains_record_ids(self) -> None:
        runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="trace-bundle"), fixture=self.fixture)
        from glio_noncode.cell_state_frontier_observability import (
            CellStateFrontierStage,
            build_cell_state_frontier_trace,
        )
        trace = build_cell_state_frontier_trace(runtime)
        bundle = next(item for item in trace.events if item.stage is CellStateFrontierStage.BUNDLE)
        self.assertEqual(len(bundle.record_ids), 16)

    def test_runtime_comparison_has_no_state_changes(self) -> None:
        left = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="left"), fixture=self.fixture)
        right = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="right"), fixture=self.fixture)
        comparison = compare_cell_state_frontier_runs(left, right)
        self.assertTrue(comparison.equivalent)
        self.assertEqual(comparison.state_changes, ())

    def test_runtime_comparison_detects_state_change(self) -> None:
        left = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id="left"), fixture=self.fixture)
        altered_receipts = (
            replace(left.quality.bundle.evaluation.receipts[0], adapter_state="partial"),
            *left.quality.bundle.evaluation.receipts[1:],
        )
        altered_evaluation = replace(left.quality.bundle.evaluation, receipts=altered_receipts)
        altered_bundle = replace(left.quality.bundle, evaluation=altered_evaluation)
        right_quality = replace(left.quality, bundle=altered_bundle)
        right = replace(left, run_id="right", quality=right_quality)
        comparison = compare_cell_state_frontier_runs(left, right)
        self.assertFalse(comparison.equivalent)
        self.assertIn("C13-POS-001", {item[0] for item in comparison.state_changes})

    def test_review_budget_all_rows_is_twelve(self) -> None:
        from glio_noncode.cell_state_frontier_observability import cell_state_frontier_review_budget
        budget = cell_state_frontier_review_budget(self.view)
        self.assertEqual(budget["eligible_review_count"], 12)

    def test_review_budget_priority_two_is_eight(self) -> None:
        from glio_noncode.cell_state_frontier_observability import cell_state_frontier_review_budget
        budget = cell_state_frontier_review_budget(self.view, maximum_priority=2)
        self.assertEqual(budget["eligible_review_count"], 8)

    def test_review_budget_ids_are_subset(self) -> None:
        from glio_noncode.cell_state_frontier_observability import cell_state_frontier_review_budget
        all_rows = cell_state_frontier_review_budget(self.view)
        limited = cell_state_frontier_review_budget(self.view, maximum_priority=2)
        self.assertTrue(set(limited["eligible_record_ids"]) <= set(all_rows["eligible_record_ids"]))


if __name__ == "__main__":
    unittest.main()
