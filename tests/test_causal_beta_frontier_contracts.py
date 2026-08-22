from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.causal_beta import CausalBetaState
from glio_noncode.causal_beta_frontier_adapters import execute_causal_beta_frontier_record
from glio_noncode.causal_beta_frontier_contracts import build_causal_beta_frontier_contracts
from glio_noncode.causal_beta_frontier_fixture_eval import evaluate_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_integrity import evaluate_causal_beta_frontier_integrity
from glio_noncode.causal_beta_frontier_lineage import build_causal_beta_frontier_lineage
from glio_noncode.causal_beta_frontier_metrics import build_causal_beta_frontier_metrics
from glio_noncode.causal_beta_frontier_policy import default_causal_beta_frontier_policy
from glio_noncode.causal_beta_frontier_provenance import build_causal_beta_frontier_provenance
from glio_noncode.causal_beta_frontier_public_data import CausalBetaFrontierOperation, CausalBetaFrontierRole, default_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_reconciliation import reconcile_causal_beta_frontier
from glio_noncode.causal_beta_frontier_review import build_causal_beta_frontier_review_queue
from glio_noncode.causal_beta_frontier_schema import validate_causal_beta_frontier_schema


class CausalBetaFrontierContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_causal_beta_frontier_fixture()
        cls.evaluation = evaluate_causal_beta_frontier_fixture(cls.fixture)
        cls.contracts = build_causal_beta_frontier_contracts()
        cls.schema = validate_causal_beta_frontier_schema(cls.fixture, cls.evaluation)
        cls.metrics = build_causal_beta_frontier_metrics(cls.evaluation, cls.fixture)
        cls.policy = default_causal_beta_frontier_policy()
        cls.decisions = cls.policy.decide(cls.evaluation)
        cls.review = build_causal_beta_frontier_review_queue(cls.evaluation, cls.policy)
        cls.reconciliation = reconcile_causal_beta_frontier(cls.fixture, cls.evaluation, cls.decisions, cls.policy)
        cls.lineage = build_causal_beta_frontier_lineage(cls.fixture, cls.evaluation)
        cls.provenance = build_causal_beta_frontier_provenance(cls.fixture, cls.evaluation)

    def test_contract_ids_are_domain11_beta_ids(self) -> None:
        self.assertEqual({item.contract_id for item in self.contracts.contracts}, {"causal-beta-c05-contract", "causal-beta-c06-contract", "causal-beta-c07-contract", "causal-beta-c08-contract"})
        self.assertEqual({item.capability_id for item in self.contracts.contracts}, {"GNC-D11-C05", "GNC-D11-C06", "GNC-D11-C07", "GNC-D11-C08"})

    def test_contract_lookup_by_capability_and_operation_agrees(self) -> None:
        for contract in self.contracts.contracts:
            self.assertIs(self.contracts.for_capability(contract.capability_id), contract)
            self.assertIs(self.contracts.for_operation(contract.operation), contract)

    def test_contract_inputs_are_operation_specific(self) -> None:
        mediator_fields = {"source_node", "target_node", "context_key", "evidence"}
        for operation in (CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, CausalBetaFrontierOperation.ELEMENT_TO_GENE, CausalBetaFrontierOperation.GENE_TO_STATE):
            self.assertEqual(set(self.contracts.for_operation(operation).required_fields), mediator_fields)
        allele = self.contracts.for_operation(CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE)
        self.assertEqual(set(allele.required_fields), {"state_id", "context_key", "observations"})

    def test_contract_outputs_are_nonempty_and_unique(self) -> None:
        for contract in self.contracts.contracts:
            self.assertTrue(contract.output_fields)
            self.assertEqual(len(contract.output_fields), len(set(contract.output_fields)))
            self.assertTrue(contract.issue_codes)
            self.assertEqual(len(contract.issue_codes), len(set(contract.issue_codes)))

    def test_contract_addresses_are_stable(self) -> None:
        again = build_causal_beta_frontier_contracts()
        self.assertEqual(self.contracts.content_address, again.content_address)
        for left, right in zip(self.contracts.contracts, again.contracts):
            self.assertEqual(left.content_address, right.content_address)

    def test_public_sources_are_https_receipts(self) -> None:
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len({item.source_id for item in self.fixture.sources}), 5)
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))
        self.assertTrue(all(item.release for item in self.fixture.sources))
        self.assertTrue(all(item.scope for item in self.fixture.sources))

    def test_source_scopes_cover_each_operation_family(self) -> None:
        scopes = " ".join(item.scope for item in self.fixture.sources).lower()
        self.assertIn("regulatory", scopes)
        self.assertIn("topology", scopes)
        self.assertIn("expression", scopes)
        self.assertIn("state", scopes)
        self.assertIn("method", scopes)

    def test_mediator_payloads_have_two_evidence_rows_for_positive_cases(self) -> None:
        for record in self.fixture.positive_records:
            if record.operation is CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE:
                continue
            self.assertEqual(len(record.payload["evidence"]), 2)
            self.assertEqual(len({item["source_id"] for item in record.payload["evidence"]}), 2)
            self.assertTrue(all(item["context_key"] == self.fixture.context_key for item in record.payload["evidence"]))

    def test_allele_payload_has_reference_and_alternate_observations(self) -> None:
        record = self.fixture.operation_records(CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE)[0]
        observations = record.payload["observations"]
        self.assertEqual({item["allele"] for item in observations}, {"reference", "alternate"})
        self.assertEqual({item["state_id"] for item in observations}, {"state:open"})
        self.assertTrue(all(item["raw_hash"].startswith("sha256:") for item in observations))

    def test_control_payloads_are_intentionally_incomplete_or_conflicting(self) -> None:
        partial = [item for item in self.fixture.control_records if item.expected_state is CausalBetaState.PARTIAL]
        contradictory = [item for item in self.fixture.control_records if item.expected_state is CausalBetaState.CONTRADICTORY]
        ambiguous = [item for item in self.fixture.control_records if item.expected_state is CausalBetaState.AMBIGUOUS]
        foreign = [item for item in self.fixture.control_records if item.expected_state is CausalBetaState.OUT_OF_DOMAIN]
        self.assertEqual(len(partial), 4)
        self.assertEqual(len(contradictory), 3)
        self.assertEqual(len(ambiguous), 1)
        self.assertEqual(len(foreign), 4)

    def test_mediator_adapter_results_keep_primitive_receipts(self) -> None:
        for record in self.fixture.records:
            result = execute_causal_beta_frontier_record(record)
            self.assertTrue(result.primitive_address == "" or result.primitive_address.startswith("sha256:"))
            self.assertTrue(result.content_address.startswith("sha256:"))
            if record.operation is not CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE and result.source_ids:
                self.assertTrue(result.source_versions)

    def test_adapter_results_have_expected_source_count_floor(self) -> None:
        for record in self.fixture.records:
            result = execute_causal_beta_frontier_record(record)
            if record.expected_state is CausalBetaState.SUPPORTED:
                self.assertGreaterEqual(len(result.source_ids), 2)
            if record.expected_state is CausalBetaState.OUT_OF_DOMAIN:
                self.assertEqual(result.source_ids, ())

    def test_evaluation_rows_match_contract_operations(self) -> None:
        contract_ops = {item.operation.value for item in self.contracts.contracts}
        self.assertEqual({item.operation for item in self.evaluation.rows}, contract_ops)
        for row in self.evaluation.rows:
            self.assertIn(row.expected_state, {item.value for item in CausalBetaState})
            self.assertEqual(row.record_id, row.adapter.record_id)

    def test_evaluation_issue_floors_are_subsets_of_observed_issues(self) -> None:
        for row in self.evaluation.rows:
            self.assertTrue(set(row.expected_issue_codes) <= set(row.observed_issue_codes))
            self.assertTrue(row.issue_match)

    def test_metrics_conserve_operation_counts(self) -> None:
        self.assertEqual(sum(item.record_count for item in self.metrics.operations), 16)
        self.assertEqual(sum(item.positive_count for item in self.metrics.operations), 4)
        self.assertEqual(sum(item.control_count for item in self.metrics.operations), 12)
        self.assertEqual(sum(item.state_matches for item in self.metrics.operations), 16)
        self.assertEqual(sum(item.issue_matches for item in self.metrics.operations), 16)

    def test_schema_checks_are_all_named_and_boolean(self) -> None:
        self.assertTrue(self.schema.accepted)
        self.assertEqual(len(self.schema.checks), 7)
        self.assertEqual(len({item["check_id"] for item in self.schema.checks}), 7)
        self.assertTrue(all(isinstance(item["passed"], bool) for item in self.schema.checks))

    def test_schema_field_meanings_are_not_empty(self) -> None:
        self.assertTrue(all(item.meaning for item in self.schema.fields))
        self.assertTrue(all(item.value_type for item in self.schema.fields))
        self.assertEqual(len({item.name for item in self.schema.fields}), 10)

    def test_policy_retains_only_supported_positive_rows(self) -> None:
        for decision in self.decisions:
            if decision.decision.value == "retain":
                self.assertTrue(decision.publishable)
                self.assertEqual(decision.role, CausalBetaFrontierRole.POSITIVE.value)
                self.assertEqual(decision.state, CausalBetaState.SUPPORTED.value)
            else:
                self.assertFalse(decision.publishable)

    def test_policy_rules_cover_all_observed_state_operation_pairs(self) -> None:
        pairs = {(item.operation, item.state) for item in self.decisions}
        rules = {(item.operation.value, item.state) for item in self.policy.rules}
        self.assertTrue(pairs <= rules)
        self.assertEqual(len(rules), 16)

    def test_review_queue_required_checks_reflect_issue_codes(self) -> None:
        evaluation_map = {item.record_id: item for item in self.evaluation.rows}
        for review in self.review.items:
            issues = set(evaluation_map[review.record_id].observed_issue_codes)
            if issues:
                self.assertTrue(any(code.removeprefix("check:") in issues for code in review.required_checks))
            else:
                self.assertEqual(review.required_checks, ("check:positive-receipt",))

    def test_reconciliation_mismatch_kind_is_empty_for_exact_replay(self) -> None:
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.reconciliation.mismatch_record_ids, ())
        self.assertTrue(all(item.mismatch_kinds == () for item in self.reconciliation.items))

    def test_reconciliation_policy_decisions_are_joined(self) -> None:
        decision_map = {item.record_id: item for item in self.decisions}
        for item in self.reconciliation.items:
            self.assertEqual(item.policy_decision, decision_map[item.record_id].decision.value)
            self.assertEqual(item.policy_rule_id, decision_map[item.record_id].rule_id)

    def test_lineage_source_edges_match_record_source_ids(self) -> None:
        for record in self.fixture.records:
            source_edges = self.lineage.for_record(record.record_id)
            source_ids = {item.parent_id.removeprefix("source:") for item in source_edges if item.edge_kind == "source_to_record"}
            self.assertEqual(source_ids, set(record.source_ids))

    def test_lineage_result_edges_match_evaluation_addresses(self) -> None:
        result_addresses = {item.adapter.content_address for item in self.evaluation.rows}
        lineage_addresses = {item.child_id.removeprefix("result:") for item in self.lineage.record_edges}
        self.assertEqual(result_addresses, lineage_addresses)

    def test_provenance_nodes_match_sources_records_and_results(self) -> None:
        kinds = {item.node_kind for item in self.provenance.nodes}
        self.assertEqual(kinds, {"source", "fixture", "record", "result"})
        self.assertEqual(sum(item.node_kind == "source" for item in self.provenance.nodes), 5)
        self.assertEqual(sum(item.node_kind == "record" for item in self.provenance.nodes), 16)
        self.assertEqual(sum(item.node_kind == "result" for item in self.provenance.nodes), 16)
        self.assertEqual(sum(item.node_kind == "fixture" for item in self.provenance.nodes), 1)

    def test_integrity_check_ids_are_closed(self) -> None:
        report = evaluate_causal_beta_frontier_integrity(self.fixture, self.evaluation, self.lineage, self.provenance)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 9)
        expected = {"fixture-address", "record-addresses", "source-resolution", "evaluation-addresses", "lineage-results", "provenance-accepted", "unique-sources", "unique-records", "unique-lineage"}
        self.assertEqual({item.check_id for item in report.checks}, expected)

    def test_jsonable_contract_payload_is_json_safe(self) -> None:
        payload = self.contracts.to_dict()
        decoded = json.loads(json.dumps(payload, default=str))
        self.assertEqual(len(decoded["contracts"]), 4)
        self.assertTrue(decoded["accepted"])
        self.assertTrue(all(item["content_address"].startswith("sha256:") for item in decoded["contracts"]))

    def test_jsonable_evaluation_payload_is_json_safe(self) -> None:
        decoded = json.loads(json.dumps(self.evaluation.to_dict(), default=str))
        self.assertEqual(decoded["state_match_count"], 16)
        self.assertEqual(len(decoded["rows"]), 16)
        self.assertTrue(decoded["accepted"])

    def test_jsonable_reconciliation_payload_is_json_safe(self) -> None:
        decoded = json.loads(json.dumps(self.reconciliation.to_dict(), default=str))
        self.assertEqual(decoded["accepted_count"], 9)
        self.assertEqual(decoded["mismatch_record_ids"], [])
        self.assertTrue(decoded["reconciled"])

    def test_duplicate_record_ids_are_visible_in_schema(self) -> None:
        first = self.fixture.records[0]
        second = replace(self.fixture.records[1], record_id=first.record_id, content_address="")
        changed = replace(self.fixture, records=(first, second) + self.fixture.records[2:], content_address="")
        report = validate_causal_beta_frontier_schema(changed, self.evaluation)
        self.assertFalse(report.accepted)
        self.assertIn("record_ids", report.failed_checks)

    def test_changed_issue_floor_is_detected_by_evaluation(self) -> None:
        first = self.fixture.records[0]
        changed = replace(first, expected_issue_codes=("unexpected_issue",), content_address="")
        fixture = replace(self.fixture, records=(changed,) + self.fixture.records[1:], content_address="")
        evaluation = evaluate_causal_beta_frontier_fixture(fixture)
        self.assertFalse(evaluation.accepted)
        self.assertIn(first.record_id, evaluation.failed_record_ids)

    def test_policy_decisions_have_unique_content_addresses(self) -> None:
        addresses = [item.content_address for item in self.decisions]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(item.startswith("sha256:") for item in addresses))

    def test_review_items_have_unique_content_addresses(self) -> None:
        addresses = [item.content_address for item in self.review.items]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(item.startswith("sha256:") for item in addresses))

    def test_result_addresses_are_unique_by_record(self) -> None:
        addresses = [item.adapter.content_address for item in self.evaluation.rows]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertEqual(len(addresses), 16)

    def test_contract_limitation_texts_mark_nonclinical_scope(self) -> None:
        text = " ".join(item.limitation.lower() for item in self.contracts.contracts)
        self.assertIn("not", text)
        self.assertIn("descriptive", text)

    def test_control_roles_are_not_publishable(self) -> None:
        control_ids = {item.record_id for item in self.fixture.control_records}
        for decision in self.decisions:
            if decision.record_id in control_ids:
                self.assertFalse(decision.publishable)

    def test_positive_role_count_is_exactly_four(self) -> None:
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len({item.operation for item in self.fixture.positive_records}), 4)
        self.assertTrue(all(item.role is CausalBetaFrontierRole.POSITIVE for item in self.fixture.positive_records))

    def test_control_role_count_is_exactly_twelve(self) -> None:
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(all(item.role is CausalBetaFrontierRole.CONTROL for item in self.fixture.control_records))


if __name__ == "__main__":
    unittest.main()
