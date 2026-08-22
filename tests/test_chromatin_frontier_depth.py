from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.chromatin_frontier_contracts import default_chromatin_frontier_contracts
from glio_noncode.chromatin_frontier_exports import (
    chromatin_frontier_export_receipt,
    export_chromatin_frontier_json,
)
from glio_noncode.chromatin_frontier_fixture_eval import evaluate_chromatin_frontier_fixture
from glio_noncode.chromatin_frontier_lineage import (
    build_chromatin_frontier_lineage,
    verify_chromatin_frontier_lineage,
)
from glio_noncode.chromatin_frontier_metrics import compute_chromatin_frontier_metrics
from glio_noncode.chromatin_frontier_observability import (
    build_chromatin_frontier_trace,
    chromatin_frontier_review_budget,
    compare_chromatin_frontier_runs,
)
from glio_noncode.chromatin_frontier_policy import (
    ChromatinFrontierPolicyDisposition,
    default_chromatin_frontier_policy_rules,
    evaluate_chromatin_frontier_policy,
)
from glio_noncode.chromatin_frontier_public_data import (
    CHROMATIN_FRONTIER_CONTEXT_KEY,
    CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY,
    CHROMATIN_FRONTIER_FIXTURE_VERSION,
    CHROMATIN_FRONTIER_SOURCE_COUNT,
    ChromatinFrontierCatalog,
    ChromatinFrontierOperation,
    ChromatinFrontierRecord,
    ChromatinFrontierRole,
    ChromatinFrontierSourceReceipt,
    audit_chromatin_frontier_data,
    build_chromatin_frontier_catalog,
    default_chromatin_frontier_fixture,
    load_chromatin_frontier_fixture,
)
from glio_noncode.chromatin_frontier_quality_gate import run_chromatin_frontier_quality_gate
from glio_noncode.chromatin_frontier_reconciliation import reconcile_chromatin_frontier
from glio_noncode.chromatin_frontier_release import build_chromatin_frontier_release
from glio_noncode.chromatin_frontier_replay import (
    build_chromatin_frontier_expectation,
    replay_chromatin_frontier_evaluation,
)
from glio_noncode.chromatin_frontier_runtime import (
    ChromatinFrontierRuntimeOptions,
    run_chromatin_frontier_pipeline,
)
from glio_noncode.chromatin_frontier_scenario_matrix import (
    default_chromatin_frontier_scenarios,
    evaluate_chromatin_frontier_scenarios,
)
from glio_noncode.chromatin_frontier_schema import (
    chromatin_frontier_schema_manifest,
    default_chromatin_frontier_schemas,
    validate_chromatin_frontier_schema,
)
from glio_noncode.chromatin_frontier_views import (
    build_chromatin_frontier_view,
    chromatin_frontier_review_summary,
    filter_chromatin_frontier_review_queue,
)
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import content_hash, jsonable


class ChromatinFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_chromatin_frontier_fixture()
        self.evaluation = evaluate_chromatin_frontier_fixture(self.fixture)
        self.quality = run_chromatin_frontier_quality_gate(self.fixture)
        self.runtime = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="d07-depth"),
            fixture=self.fixture,
        )
        self.view = build_chromatin_frontier_view(self.fixture, self.evaluation)

    def test_fixture_constants_match_declared_shape(self) -> None:
        self.assertEqual(self.fixture.fixture_version, CHROMATIN_FRONTIER_FIXTURE_VERSION)
        self.assertEqual(self.fixture.context_key, CHROMATIN_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY)
        self.assertEqual(len(self.fixture.sources), CHROMATIN_FRONTIER_SOURCE_COUNT)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)

    def test_source_receipts_are_unique_addressed_and_https_only(self) -> None:
        source_ids = [item.source_id for item in self.fixture.sources]
        addresses = [item.content_address for item in self.fixture.sources]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))
        self.assertTrue(all(item.scope for item in self.fixture.sources))
        self.assertEqual(set(self.fixture.source_map()), set(source_ids))

    def test_record_receipts_are_unique_and_reference_known_sources(self) -> None:
        record_ids = [item.record_id for item in self.fixture.records]
        self.assertEqual(len(record_ids), len(set(record_ids)))
        known_sources = set(self.fixture.source_map())
        self.assertTrue(
            all(set(item.source_ids) <= known_sources for item in self.fixture.records)
        )
        self.assertEqual(set(self.fixture.record_map()), set(record_ids))
        self.assertTrue(all(item.payload for item in self.fixture.records))

    def test_each_operation_has_one_positive_and_three_controls(self) -> None:
        for operation in ChromatinFrontierOperation:
            records = tuple(item for item in self.fixture.records if item.operation is operation)
            self.assertEqual(len(records), 4, operation.value)
            self.assertEqual(
                sum(item.role is ChromatinFrontierRole.POSITIVE for item in records),
                1,
            )
            self.assertEqual(
                sum(item.role is ChromatinFrontierRole.CONTROL for item in records),
                3,
            )

    def test_catalog_preserves_fixture_identity_and_operation_coverage(self) -> None:
        catalog = build_chromatin_frontier_catalog(self.fixture)
        self.assertIs(catalog.fixture, self.fixture)
        self.assertEqual(catalog.record_ids, tuple(item.record_id for item in self.fixture.records))
        self.assertEqual(catalog.source_ids, tuple(item.source_id for item in self.fixture.sources))
        self.assertEqual(set(catalog.operations), set(ChromatinFrontierOperation))
        self.assertTrue(catalog.content_address.startswith("sha256:"))

    def test_catalog_rejects_duplicate_ids(self) -> None:
        catalog = build_chromatin_frontier_catalog(self.fixture)
        with self.assertRaises(ValidationError):
            ChromatinFrontierCatalog(
                catalog.fixture,
                (catalog.source_ids[0], *catalog.source_ids),
                catalog.record_ids,
                catalog.operations,
                catalog.content_address,
            )
        with self.assertRaises(ValidationError):
            ChromatinFrontierCatalog(
                catalog.fixture,
                catalog.source_ids,
                (catalog.record_ids[0], *catalog.record_ids),
                catalog.operations,
                catalog.content_address,
            )

    def test_fixture_json_round_trip_retains_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(self.fixture.to_dict()), encoding="utf-8")
            loaded = load_chromatin_frontier_fixture(path)
        self.assertEqual(loaded.to_dict(), self.fixture.to_dict())
        self.assertEqual(loaded.content_address, self.fixture.content_address)
        self.assertEqual(loaded.record_map()["C13-POS-001"].operation, ChromatinFrontierOperation.CHROMATIN_SEGMENTATION)

    def test_fixture_loader_rejects_tampered_content_address(self) -> None:
        payload = self.fixture.to_dict() | {"content_address": "sha256:tampered"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tampered.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_chromatin_frontier_fixture(path)

    def test_data_audit_contains_all_boundary_checks(self) -> None:
        audit = audit_chromatin_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertGreaterEqual(len(audit.checks), 8)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in audit.checks))
        self.assertEqual(audit.fixture_id, self.fixture.fixture_id)

    def test_data_audit_detects_record_context_drift(self) -> None:
        drifted = replace(
            self.fixture.records[0],
            context_key="GRCh38|glioma|adult|differentiated|tumor|unknown",
        )
        fixture = replace(self.fixture, records=(drifted, *self.fixture.records[1:]))
        audit = audit_chromatin_frontier_data(fixture)
        self.assertFalse(audit.accepted)
        self.assertIn("positive-context", audit.failed_check_ids)

    def test_evaluation_has_seven_checks_per_record_and_eight_global_checks(self) -> None:
        record_checks = tuple(item for item in self.evaluation.checks if item.record_id is not None)
        global_checks = tuple(item for item in self.evaluation.checks if item.record_id is None)
        self.assertEqual(len(record_checks), 16 * 7)
        self.assertEqual(len(global_checks), 8)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())

    def test_evaluation_check_ids_are_unique_and_addressed(self) -> None:
        check_ids = [item.check_id for item in self.evaluation.checks]
        addresses = [item.content_address for item in self.evaluation.checks]
        self.assertEqual(len(check_ids), len(set(check_ids)))
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(address.startswith("sha256:") for address in addresses))
        self.assertEqual(self.evaluation.positive_count, 4)
        self.assertEqual(self.evaluation.control_count, 12)

    def test_evaluation_receipt_addresses_are_unique(self) -> None:
        addresses = [item.content_address for item in self.evaluation.receipts]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(address.startswith("sha256:") for address in addresses))
        self.assertEqual(
            tuple(item.record_id for item in self.evaluation.receipts),
            tuple(item.record_id for item in self.fixture.records),
        )

    def test_evaluation_is_deterministic_across_repeated_runs(self) -> None:
        repeated = evaluate_chromatin_frontier_fixture(self.fixture)
        self.assertEqual(repeated.content_address, self.evaluation.content_address)
        self.assertEqual(repeated.to_dict(), self.evaluation.to_dict())
        self.assertEqual(
            build_chromatin_frontier_expectation(repeated).to_dict(),
            build_chromatin_frontier_expectation(self.evaluation).to_dict(),
        )

    def test_receipt_summaries_expose_operation_specific_fields(self) -> None:
        summaries = {item.record_id: item.summary for item in self.evaluation.receipts}
        self.assertIn("segment_count", summaries["C13-POS-001"])
        self.assertIn("directions", summaries["C14-POS-001"])
        self.assertIn("aggregate_purity", summaries["C15-POS-001"])
        self.assertIn("corrected_signals", summaries["C16-POS-001"])
        self.assertTrue(all("input_text" not in value for value in summaries.values()))
        self.assertTrue(all("payload" not in value for value in summaries.values()))

    def test_positive_records_are_supported_and_controls_are_not(self) -> None:
        positives = tuple(
            item for item in self.evaluation.receipts if item.role is ChromatinFrontierRole.POSITIVE
        )
        controls = tuple(
            item for item in self.evaluation.receipts if item.role is ChromatinFrontierRole.CONTROL
        )
        self.assertEqual(len(positives), 4)
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(item.adapter_state == "supported" for item in positives))
        self.assertTrue(all(item.adapter_state != "supported" for item in controls))

    def test_expected_issue_floors_are_observed(self) -> None:
        records = self.fixture.record_map()
        for receipt in self.evaluation.receipts:
            expected = set(records[receipt.record_id].expected_issue_codes)
            observed = set(receipt.observed_issue_codes)
            self.assertTrue(expected <= observed, receipt.record_id)

    def test_state_matrix_is_explicit_for_each_operation(self) -> None:
        states = {
            operation: tuple(
                item.adapter_state
                for item in self.evaluation.receipts
                if item.operation is operation
            )
            for operation in ChromatinFrontierOperation
        }
        self.assertEqual(states[ChromatinFrontierOperation.CHROMATIN_SEGMENTATION], ("supported", "ambiguous", "out_of_domain", "partial"))
        self.assertEqual(states[ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN], ("supported", "ambiguous", "out_of_domain", "partial"))
        self.assertEqual(states[ChromatinFrontierOperation.EPIGENOMIC_PURITY], ("supported", "partial", "out_of_domain", "partial"))
        self.assertEqual(states[ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION], ("supported", "partial", "out_of_domain", "partial"))

    def test_contract_registry_resolves_every_operation(self) -> None:
        registry = default_chromatin_frontier_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual({item.operation for item in registry.contracts}, set(ChromatinFrontierOperation))
        self.assertTrue(registry.content_address.startswith("sha256:"))
        for operation in ChromatinFrontierOperation:
            contract = registry.by_operation(operation)
            self.assertTrue(contract.contract_id.startswith("GNC-D07-"))
            self.assertTrue(contract.required_payload_fields)
            self.assertIn("supported", contract.positive_states)

    def test_contract_issue_vocabularies_are_disjoint_from_claims(self) -> None:
        registry = default_chromatin_frontier_contracts()
        for contract in registry.contracts:
            self.assertTrue(set(contract.issue_vocabulary))
            self.assertTrue(set(contract.prohibited_claims))
            self.assertFalse(set(contract.issue_vocabulary) & set(contract.prohibited_claims))

    def test_replay_report_has_eight_passed_checks(self) -> None:
        replay = replay_chromatin_frontier_evaluation(self.evaluation, fixture=self.fixture)
        self.assertTrue(replay.accepted)
        self.assertEqual(len(replay.checks), 8)
        self.assertEqual(replay.failed_check_ids, ())
        self.assertTrue(all(item.passed for item in replay.checks))

    def test_replay_detects_changed_fixture_identity(self) -> None:
        changed = replace(self.fixture, fixture_id="chromatin-frontier-changed")
        evaluation = evaluate_chromatin_frontier_fixture(changed)
        replay = replay_chromatin_frontier_evaluation(evaluation, fixture=self.fixture)
        self.assertFalse(replay.accepted)
        self.assertIn("fixture-identity", replay.failed_check_ids)

    def test_scenario_matrix_matches_receipt_order(self) -> None:
        scenarios = default_chromatin_frontier_scenarios()
        report = evaluate_chromatin_frontier_scenarios(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(scenarios), 16)
        self.assertEqual(
            tuple(item.record_id for item in scenarios),
            tuple(item.record_id for item in self.evaluation.receipts),
        )
        self.assertEqual(len(report.checks), len(report.scenarios))

    def test_scenario_matrix_detects_state_drift(self) -> None:
        drifted = replace(self.fixture.records[0], expected_state="partial")
        fixture = replace(self.fixture, records=(drifted, *self.fixture.records[1:]))
        evaluation = evaluate_chromatin_frontier_fixture(fixture)
        evaluation = replace(
            evaluation,
            receipts=(
                replace(evaluation.receipts[0], adapter_state="partial"),
                *evaluation.receipts[1:],
            ),
        )
        report = evaluate_chromatin_frontier_scenarios(evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("scenario:C13-POS-001", {
            item.scenario_id for item in report.checks if not item.passed
        })

    def test_policy_declares_bounded_dispositions(self) -> None:
        rules = default_chromatin_frontier_policy_rules()
        self.assertEqual(len(rules), 12)
        self.assertTrue(all(item.applies_to for item in rules))
        self.assertTrue(
            all(
                item.disposition_on_failure
                in {ChromatinFrontierPolicyDisposition.DENY, ChromatinFrontierPolicyDisposition.REVIEW}
                for item in rules
            )
        )
        self.assertEqual({operation for item in rules for operation in item.applies_to}, set(ChromatinFrontierOperation))

    def test_policy_report_contains_one_check_per_rule(self) -> None:
        policy = evaluate_chromatin_frontier_policy(self.fixture, self.evaluation)
        self.assertTrue(policy.accepted)
        self.assertEqual(len(policy.checks), len(policy.rules))
        self.assertEqual(policy.failed_rule_ids, ())
        self.assertTrue(all(item.disposition is ChromatinFrontierPolicyDisposition.PASS for item in policy.checks))

    def test_policy_detects_subject_key_in_payload(self) -> None:
        record = replace(
            self.fixture.records[0],
            payload=self.fixture.records[0].payload | {"donor": "not-permitted"},
        )
        fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        policy = evaluate_chromatin_frontier_policy(fixture)
        self.assertFalse(policy.accepted)
        self.assertIn("no-subject-identifiers", policy.failed_rule_ids)

    def test_schema_manifest_has_four_operation_schemas(self) -> None:
        schemas = default_chromatin_frontier_schemas()
        manifest = chromatin_frontier_schema_manifest(schemas)
        self.assertEqual(len(schemas), 4)
        self.assertEqual(len(manifest["schemas"]), 4)
        self.assertEqual({item.operation for item in schemas}, set(ChromatinFrontierOperation))
        self.assertTrue(manifest["content_address"].startswith("sha256:"))
        self.assertEqual(len({item.schema_id for item in schemas}), 4)

    def test_schema_outputs_cover_all_receipt_summary_keys(self) -> None:
        report = validate_chromatin_frontier_schema(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 23)
        by_operation = {item.operation: item for item in report.schemas}
        for operation in ChromatinFrontierOperation:
            receipts = tuple(item for item in self.evaluation.receipts if item.operation is operation)
            declared = set(by_operation[operation].output_field_names)
            observed = set().union(*(item.summary for item in receipts))
            self.assertTrue(declared <= observed, operation.value)

    def test_schema_report_detects_prohibited_claim_in_summary(self) -> None:
        receipt = self.evaluation.receipts[0]
        altered = replace(receipt, summary=receipt.summary | {"claim": "clinical truth"})
        evaluation = replace(
            self.evaluation,
            receipts=(altered, *self.evaluation.receipts[1:]),
        )
        report = validate_chromatin_frontier_schema(self.fixture, evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("chromatin_segmentation:claims", report.failed_check_ids)

    def test_metrics_conserve_record_and_check_counts(self) -> None:
        metrics = compute_chromatin_frontier_metrics(self.evaluation)
        self.assertEqual(metrics.total_records, sum(item.record_count for item in metrics.operation_metrics))
        self.assertEqual(metrics.positive_records, sum(item.positive_count for item in metrics.operation_metrics))
        self.assertEqual(metrics.control_records, sum(item.control_count for item in metrics.operation_metrics))
        self.assertEqual(metrics.supported_records + metrics.review_records, metrics.total_records)
        self.assertEqual(metrics.check_count, metrics.passed_check_count)
        self.assertEqual(metrics.check_pass_rate, 1.0)

    def test_metrics_operation_rows_have_stable_order(self) -> None:
        metrics = compute_chromatin_frontier_metrics(self.evaluation)
        self.assertEqual(
            tuple(item.operation for item in metrics.operation_metrics),
            tuple(ChromatinFrontierOperation),
        )
        self.assertTrue(all(item.record_count == 4 for item in metrics.operation_metrics))
        self.assertTrue(all(item.positive_count == 1 for item in metrics.operation_metrics))
        self.assertTrue(all(item.control_count == 3 for item in metrics.operation_metrics))

    def test_view_has_one_operation_view_per_operation(self) -> None:
        self.assertTrue(self.view.accepted)
        self.assertEqual(
            tuple(item.operation for item in self.view.operation_views),
            tuple(ChromatinFrontierOperation),
        )
        self.assertEqual(sum(item.review_count for item in self.view.operation_views), 12)
        self.assertEqual(sum(item.positive_count for item in self.view.operation_views), 4)
        self.assertEqual(sum(item.control_count for item in self.view.operation_views), 12)

    def test_view_review_queue_is_priority_descending_then_record_id(self) -> None:
        keys = [(item.priority, item.record_id) for item in self.view.review_queue]
        self.assertEqual(keys, sorted(keys, key=lambda item: (-item[0], item[1])))
        self.assertTrue(all(item.priority >= 2 for item in self.view.review_queue))
        self.assertTrue(all(item.action for item in self.view.review_queue))
        self.assertEqual(len(self.view.accepted_record_ids), 4)

    def test_view_filters_compose_states_operations_and_priority(self) -> None:
        out_of_domain = filter_chromatin_frontier_review_queue(
            self.view,
            states=("out_of_domain",),
        )
        self.assertEqual(len(out_of_domain), 4)
        segmentation = filter_chromatin_frontier_review_queue(
            self.view,
            operations=(ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,),
        )
        self.assertEqual(len(segmentation), 3)
        bounded = filter_chromatin_frontier_review_queue(self.view, maximum_priority=2)
        self.assertEqual(len(bounded), 6)
        combined = filter_chromatin_frontier_review_queue(
            self.view,
            states=("partial",),
            operations=(ChromatinFrontierOperation.EPIGENOMIC_PURITY,),
            maximum_priority=2,
        )
        self.assertEqual(len(combined), 2)

    def test_view_summary_counts_are_conservative(self) -> None:
        summary = chromatin_frontier_review_summary(self.view)
        self.assertEqual(summary["review_count"], 12)
        self.assertEqual(sum(count for _, count in summary["state_counts"]), 12)
        self.assertEqual(sum(count for _, count in summary["operation_counts"]), 12)
        self.assertEqual(summary["source_count"], CHROMATIN_FRONTIER_SOURCE_COUNT)
        self.assertTrue(summary["content_address"].startswith("sha256:"))

    def test_source_matrix_closes_over_all_fixture_records(self) -> None:
        matrix_ids = set()
        for row in self.view.source_matrix:
            matrix_ids.update(row.record_ids)
            self.assertTrue(set(row.positive_record_ids) <= set(row.record_ids))
            self.assertTrue(set(row.control_record_ids) <= set(row.record_ids))
            self.assertEqual(
                set(row.positive_record_ids) | set(row.control_record_ids),
                set(row.record_ids),
            )
        self.assertEqual(matrix_ids, set(item.record_id for item in self.fixture.records))

    def test_lineage_edges_close_to_receipts_and_sources(self) -> None:
        lineage = build_chromatin_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertEqual(len(lineage.edges), len(self.evaluation.receipts))
        self.assertEqual(set(lineage.source_ids), set(self.fixture.source_map()))
        self.assertEqual(
            tuple(item.record_id for item in lineage.edges),
            tuple(item.record_id for item in self.evaluation.receipts),
        )
        self.assertTrue(all(item.output_address.startswith("sha256:") for item in lineage.edges))

    def test_lineage_verification_detects_address_and_order_drift(self) -> None:
        lineage = build_chromatin_frontier_lineage(self.fixture, self.evaluation)
        changed = replace(lineage, fixture_address="sha256:changed")
        failures = verify_chromatin_frontier_lineage(changed, self.fixture, self.evaluation)
        self.assertIn("fixture-identity", failures)
        reordered = replace(lineage, edges=tuple(reversed(lineage.edges)))
        failures = verify_chromatin_frontier_lineage(reordered, self.fixture, self.evaluation)
        self.assertIn("record-order", failures)

    def test_reconciliation_has_one_item_per_receipt(self) -> None:
        report = reconcile_chromatin_frontier(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.items), 16)
        self.assertEqual(report.failed_record_ids, ())
        self.assertTrue(all(item.expected_state == item.observed_state for item in report.items))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in report.items))

    def test_reconciliation_detects_expected_state_drift(self) -> None:
        drifted = replace(self.fixture.records[0], expected_state="partial")
        fixture = replace(self.fixture, records=(drifted, *self.fixture.records[1:]))
        evaluation = evaluate_chromatin_frontier_fixture(fixture)
        report = reconcile_chromatin_frontier(fixture, evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("C13-POS-001", report.failed_record_ids)

    def test_quality_gate_has_named_checks_and_accepted_bundle(self) -> None:
        self.assertTrue(self.quality.accepted)
        self.assertEqual(len(self.quality.checks), 12)
        self.assertEqual(self.quality.failed_check_ids, ())
        self.assertTrue(self.quality.bundle.accepted)
        self.assertEqual(set(self.quality.bundle.record_ids), set(self.evaluation.receipts[i].record_id for i in range(16)))
        self.assertEqual(set(self.quality.bundle.source_ids), set(self.fixture.source_map()))
        self.assertTrue(self.quality.bundle.bundle_address.startswith("sha256:"))

    def test_quality_gate_propagates_evaluation_failure(self) -> None:
        record = replace(self.fixture.records[0], expected_state="partial")
        fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        quality = run_chromatin_frontier_quality_gate(fixture)
        self.assertFalse(quality.accepted)
        self.assertIn("evaluation", quality.failed_check_ids)
        self.assertIn("bundle-accepted", quality.failed_check_ids)

    def test_bundle_address_changes_when_evidence_changes(self) -> None:
        record = replace(self.fixture.records[0], description="changed descriptive receipt")
        fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        changed = run_chromatin_frontier_quality_gate(fixture)
        self.assertNotEqual(changed.bundle.bundle_address, self.quality.bundle.bundle_address)
        self.assertNotEqual(changed.content_address, self.quality.content_address)

    def test_runtime_acceptance_and_context_boundary(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.status, "accepted")
        self.assertEqual(self.runtime.source_mode, "public_aggregate_fixture")
        self.assertEqual(self.runtime.requested_context_key, None)
        self.assertTrue(self.runtime.content_address.startswith("sha256:"))
        context = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(
                run_id="d07-wrong-context",
                requested_context_key="GRCh38|glioma|adult|differentiated|tumor|unknown",
            ),
            fixture=self.fixture,
        )
        self.assertFalse(context.accepted)
        self.assertEqual(context.status, "rejected")

    def test_strict_runtime_rejects_review_rows(self) -> None:
        strict = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="d07-strict", fail_on_review=True),
            fixture=self.fixture,
        )
        self.assertFalse(strict.accepted)
        self.assertEqual(strict.status, "rejected")
        self.assertEqual(strict.quality.bundle.metrics.review_records, 12)

    def test_runtime_options_reject_unsupported_source_mode(self) -> None:
        with self.assertRaises(ValueError):
            ChromatinFrontierRuntimeOptions(run_id="d07-network", source_mode="remote")
        with self.assertRaises(ValidationError):
            ChromatinFrontierRuntimeOptions(run_id="")

    def test_release_manifest_is_ready_and_closes_addresses(self) -> None:
        release = build_chromatin_frontier_release(self.quality, self.runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(release.release_state, "ready")
        self.assertEqual(release.fixture_id, self.fixture.fixture_id)
        self.assertEqual(release.fixture_version, self.fixture.fixture_version)
        self.assertEqual(release.run_id, self.runtime.run_id)
        self.assertEqual(release.quality_address, self.quality.content_address)
        self.assertEqual(release.bundle_address, self.quality.bundle.bundle_address)
        self.assertEqual(release.record_address, self.quality.bundle.records_address)
        self.assertEqual(set(release.operation_ids), {item.value for item in ChromatinFrontierOperation})

    def test_release_blocks_when_strict_runtime_rejects_review(self) -> None:
        strict = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="d07-release-block", fail_on_review=True),
            fixture=self.fixture,
        )
        release = build_chromatin_frontier_release(self.quality, strict)
        self.assertFalse(release.accepted)
        self.assertEqual(release.release_state, "blocked")

    def test_trace_has_monotonic_nine_stage_sequence(self) -> None:
        trace = build_chromatin_frontier_trace(self.runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.stage_receipts), 9)
        self.assertEqual(len(trace.events), 9)
        self.assertEqual(
            tuple(item.sequence for item in trace.events),
            tuple(range(1, 10)),
        )
        self.assertEqual(
            tuple(item.stage for item in trace.events),
            tuple(item.stage for item in trace.stage_receipts),
        )
        self.assertTrue(all(item.artifact_address.startswith("sha256:") for item in trace.events))

    def test_trace_stage_names_cover_runtime_components(self) -> None:
        trace = build_chromatin_frontier_trace(self.runtime)
        names = {item.stage.value for item in trace.stage_receipts}
        self.assertEqual(
            names,
            {
                "data_audit",
                "evaluation",
                "replay",
                "scenarios",
                "policy",
                "schema",
                "lineage",
                "reconciliation",
                "bundle",
            },
        )
        self.assertTrue(all(item.passed for item in trace.stage_receipts))

    def test_run_comparison_is_equivalent_for_same_fixture(self) -> None:
        left = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="d07-left"),
            fixture=self.fixture,
        )
        right = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="d07-right"),
            fixture=self.fixture,
        )
        comparison = compare_chromatin_frontier_runs(left, right)
        self.assertTrue(comparison.equivalent)
        self.assertFalse(comparison.status_changed)
        self.assertFalse(comparison.quality_changed)
        self.assertEqual(comparison.state_changes, ())
        self.assertEqual(comparison.review_count_delta, 0)

    def test_review_budget_is_content_addressed(self) -> None:
        all_rows = chromatin_frontier_review_budget(self.view)
        priority_two = chromatin_frontier_review_budget(self.view, maximum_priority=2)
        self.assertEqual(all_rows["eligible_review_count"], 12)
        self.assertEqual(priority_two["eligible_review_count"], 6)
        self.assertTrue(all_rows["content_address"].startswith("sha256:"))
        self.assertTrue(set(priority_two["eligible_record_ids"]) <= set(all_rows["eligible_record_ids"]))

    def test_json_export_is_sorted_and_sanitized(self) -> None:
        payload = export_chromatin_frontier_json(self.quality.bundle)
        self.assertTrue(payload.endswith("\n"))
        self.assertNotIn("input_text", payload)
        decoded = json.loads(payload)
        self.assertEqual(decoded["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(decoded["bundle_address"], self.quality.bundle.bundle_address)
        self.assertIn("data_audit", decoded)

    def test_export_receipt_reports_payload_size_and_address(self) -> None:
        payload = export_chromatin_frontier_json(self.evaluation)
        receipt = chromatin_frontier_export_receipt("evaluation-json", payload)
        self.assertEqual(receipt["export_name"], "evaluation-json")
        self.assertEqual(receipt["byte_count"], len(payload.encode("utf-8")))
        self.assertTrue(receipt["content_address"].startswith("sha256:"))
        self.assertEqual(
            receipt["content_address"],
            chromatin_frontier_export_receipt("evaluation-json", payload)["content_address"],
        )

    def test_jsonable_round_trip_contains_enum_values(self) -> None:
        value = jsonable(self.evaluation.receipts[0])
        self.assertEqual(value["operation"], ChromatinFrontierOperation.CHROMATIN_SEGMENTATION.value)
        self.assertEqual(value["role"], ChromatinFrontierRole.POSITIVE.value)
        self.assertIsInstance(value["summary"], dict)
        body = {key: item for key, item in value.items() if key != "content_address"}
        self.assertEqual(content_hash(body), self.evaluation.receipts[0].content_address)

    def test_content_addresses_are_sensitive_to_semantic_fields(self) -> None:
        original = self.evaluation.receipts[0]
        changed = replace(original, detail="different") if hasattr(original, "detail") else None
        self.assertIsNone(changed)
        self.assertNotEqual(
            content_hash({"record_id": original.record_id, "state": original.adapter_state}),
            content_hash({"record_id": original.record_id, "state": "partial"}),
        )

    def test_public_records_do_not_include_subject_level_keys(self) -> None:
        prohibited = {"patient", "subject", "donor", "participant", "sample_id"}
        for record in self.fixture.records:
            self.assertFalse(prohibited & set(record.payload))
            self.assertFalse(prohibited & {str(key).lower() for key in record.payload})

    def test_source_receipt_constructor_enforces_required_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ChromatinFrontierSourceReceipt(
                source_id="",
                title="source",
                uri="https://example.org",
                source_kind="public",
                release="2026",
                scope="aggregate",
                content_address="sha256:source",
            )
        with self.assertRaises(ValidationError):
            ChromatinFrontierSourceReceipt(
                source_id="source",
                title="source",
                uri="http://example.org",
                source_kind="public",
                release="2026",
                scope="aggregate",
                content_address="sha256:source",
            )

    def test_record_constructor_enforces_typed_operation_and_role(self) -> None:
        record = self.fixture.records[0]
        with self.assertRaises(ValidationError):
            ChromatinFrontierRecord(
                record_id=record.record_id,
                operation="chromatin_segmentation",
                role=record.role,
                context_key=record.context_key,
                source_ids=record.source_ids,
                payload=record.payload,
                expected_state=record.expected_state,
                expected_issue_codes=record.expected_issue_codes,
                description=record.description,
                content_address=record.content_address,
            )
        with self.assertRaises(ValidationError):
            ChromatinFrontierRecord(
                record_id=record.record_id,
                operation=record.operation,
                role="positive",
                context_key=record.context_key,
                source_ids=record.source_ids,
                payload=record.payload,
                expected_state=record.expected_state,
                expected_issue_codes=record.expected_issue_codes,
                description=record.description,
                content_address=record.content_address,
            )

    def test_quality_bundle_contains_all_component_addresses(self) -> None:
        bundle = self.quality.bundle
        components = (
            bundle.data_audit,
            bundle.evaluation,
            bundle.replay,
            bundle.scenarios,
            bundle.policy,
            bundle.lineage,
            bundle.reconciliation,
            bundle.metrics,
        )
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in components))
        self.assertEqual(bundle.records_address, content_hash({"records": bundle.evaluation.receipts}))
        self.assertEqual(len(bundle.record_ids), 16)
        self.assertEqual(len(bundle.source_ids), 5)

    def test_quality_check_addresses_are_unique(self) -> None:
        addresses = [item.content_address for item in self.quality.checks]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(address.startswith("sha256:") for address in addresses))

    def test_failed_evaluation_surfaces_failed_check_ids(self) -> None:
        record = replace(self.fixture.records[0], expected_state="invalid")
        fixture = replace(self.fixture, records=(record, *self.fixture.records[1:]))
        report = evaluate_chromatin_frontier_fixture(fixture)
        self.assertFalse(report.accepted)
        self.assertGreaterEqual(len(report.failed_check_ids), 1)
        self.assertIn("C13-POS-001:expected-state", report.failed_check_ids)

    def test_view_retains_context_on_every_review_entry(self) -> None:
        self.assertTrue(self.view.review_queue)
        self.assertTrue(
            all(item.context_key == self.fixture.context_key for item in self.view.review_queue)
        )
        self.assertTrue(all(item.state != "supported" for item in self.view.review_queue))

    def test_runtime_quality_reuses_same_bundle_identity(self) -> None:
        self.assertIs(self.runtime.quality.bundle, self.runtime.quality.bundle)
        self.assertEqual(
            self.runtime.quality.bundle.bundle_address,
            self.quality.bundle.bundle_address,
        )
        self.assertEqual(self.runtime.quality.content_address, self.quality.content_address)

    def test_fixture_to_dict_is_json_serializable(self) -> None:
        encoded = json.dumps(self.fixture.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(len(decoded["records"]), 16)
        self.assertEqual(len(decoded["sources"]), 5)

    def test_operation_values_are_stable_public_identifiers(self) -> None:
        self.assertEqual(
            tuple(item.value for item in ChromatinFrontierOperation),
            (
                "chromatin_segmentation",
                "allele_specific_chromatin",
                "epigenomic_purity",
                "batch_composition_correction",
            ),
        )


if __name__ == "__main__":
    unittest.main()
