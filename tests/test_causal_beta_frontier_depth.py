from __future__ import annotations

from dataclasses import replace
import unittest

from glio_noncode.causal_beta import CausalBetaState
from glio_noncode.causal_beta_frontier_adapters import build_causal_beta_frontier_adapters
from glio_noncode.causal_beta_frontier_artifacts import CausalBetaFrontierArtifactKind, build_causal_beta_frontier_artifact_inventory
from glio_noncode.causal_beta_frontier_contracts import build_causal_beta_frontier_contracts
from glio_noncode.causal_beta_frontier_depth import audit_causal_beta_frontier_depth
from glio_noncode.causal_beta_frontier_fixture_eval import evaluate_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_integrity import evaluate_causal_beta_frontier_integrity
from glio_noncode.causal_beta_frontier_lineage import build_causal_beta_frontier_lineage
from glio_noncode.causal_beta_frontier_metrics import build_causal_beta_frontier_metrics
from glio_noncode.causal_beta_frontier_observability import build_causal_beta_frontier_observability, record_causal_beta_frontier_event
from glio_noncode.causal_beta_frontier_policy import default_causal_beta_frontier_policy
from glio_noncode.causal_beta_frontier_provenance import build_causal_beta_frontier_provenance
from glio_noncode.causal_beta_frontier_public_data import CAUSAL_BETA_FRONTIER_CONTEXT_KEY, CausalBetaFrontierRole, audit_causal_beta_frontier_data, default_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_quality_gate import evaluate_causal_beta_frontier_quality
from glio_noncode.causal_beta_frontier_reconciliation import reconcile_causal_beta_frontier
from glio_noncode.causal_beta_frontier_release import build_causal_beta_frontier_release_manifest
from glio_noncode.causal_beta_frontier_review import build_causal_beta_frontier_review_queue
from glio_noncode.causal_beta_frontier_runtime import run_causal_beta_frontier_runtime
from glio_noncode.causal_beta_frontier_schema import validate_causal_beta_frontier_schema
from glio_noncode.causal_beta_frontier_scenario_matrix import build_causal_beta_frontier_scenario_matrix
from glio_noncode.causal_beta_frontier_validation_matrix import build_causal_beta_frontier_validation_matrix
from glio_noncode.causal_beta_frontier_bundle import assemble_causal_beta_frontier_bundle


def build_planes():
    fixture = default_causal_beta_frontier_fixture()
    evaluation = evaluate_causal_beta_frontier_fixture(fixture)
    adapters = build_causal_beta_frontier_adapters()
    contracts = build_causal_beta_frontier_contracts()
    schema = validate_causal_beta_frontier_schema(fixture, evaluation)
    metrics = build_causal_beta_frontier_metrics(evaluation, fixture)
    lineage = build_causal_beta_frontier_lineage(fixture, evaluation)
    provenance = build_causal_beta_frontier_provenance(fixture, evaluation)
    depth = audit_causal_beta_frontier_depth(fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance)
    policy = default_causal_beta_frontier_policy()
    decisions = policy.decide(evaluation)
    reconciliation = reconcile_causal_beta_frontier(fixture, evaluation, decisions, policy)
    review = build_causal_beta_frontier_review_queue(evaluation, policy)
    scenario = build_causal_beta_frontier_scenario_matrix(fixture, evaluation)
    validation = build_causal_beta_frontier_validation_matrix(fixture, evaluation)
    gate = evaluate_causal_beta_frontier_quality(fixture, evaluation, contracts, schema, metrics, lineage, reconciliation, depth, review, decisions)
    bundle = assemble_causal_beta_frontier_bundle(fixture, evaluation, metrics, contracts, schema, lineage, provenance, depth, reconciliation, policy, review, gate, scenario, validation)
    release = build_causal_beta_frontier_release_manifest(bundle, gate, depth, review)
    artifacts = build_causal_beta_frontier_artifact_inventory(fixture, evaluation, bundle, release)
    return fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance, depth, policy, decisions, reconciliation, review, scenario, validation, gate, bundle, release, artifacts


class CausalBetaFrontierDepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.planes = build_planes()
        (
            cls.fixture,
            cls.evaluation,
            cls.adapters,
            cls.contracts,
            cls.schema,
            cls.metrics,
            cls.lineage,
            cls.provenance,
            cls.depth,
            cls.policy,
            cls.decisions,
            cls.reconciliation,
            cls.review,
            cls.scenario,
            cls.validation,
            cls.gate,
            cls.bundle,
            cls.release,
            cls.artifacts,
        ) = cls.planes

    def test_all_depth_checks_have_distinct_receipts(self) -> None:
        self.assertEqual(self.depth.passed_count, self.depth.required_count)
        self.assertEqual(len({item.content_address for item in self.depth.checks}), len(self.depth.checks))
        self.assertEqual(self.depth.failed_check_ids, ())
        for item in self.depth.checks:
            self.assertTrue(item.check_id)
            self.assertTrue(item.detail)
            self.assertEqual(item.observed, item.required)

    def test_each_contract_has_unique_capability_and_operation(self) -> None:
        self.assertEqual(len({item.capability_id for item in self.contracts.contracts}), 4)
        self.assertEqual(len({item.operation for item in self.contracts.contracts}), 4)
        for contract in self.contracts.contracts:
            self.assertTrue(set(contract.issue_codes))
            self.assertTrue(set(contract.required_fields) <= {"source_node", "target_node", "context_key", "evidence", "state_id", "observations"})

    def test_schema_field_order_is_stable(self) -> None:
        self.assertEqual(tuple(item.name for item in self.schema.fields), ("record_id", "operation", "role", "context_key", "source_ids", "payload", "expected_state", "expected_issue_codes", "description", "content_address"))
        self.assertFalse(self.schema.field("expected_issue_codes").required)
        self.assertTrue(self.schema.field("content_address").required)

    def test_control_matrix_has_one_foreign_context_per_operation(self) -> None:
        foreign = self.scenario.for_control("foreign_context")
        self.assertEqual(len(foreign), 4)
        self.assertEqual({item.operation for item in foreign}, {item.value for item in self.fixture.records[0].operation.__class__})
        for scenario in foreign:
            self.assertEqual(scenario.expected_states, ("out_of_domain",))
            self.assertEqual(scenario.expected_issue_codes, ("context_mismatch",))
            self.assertTrue(scenario.accepted)

    def test_validation_matrix_has_all_cells_passed(self) -> None:
        self.assertEqual(self.validation.passed_count, 16)
        self.assertEqual(self.validation.failed_cells, ())
        self.assertEqual({item.record_id for item in self.validation.for_scenario("positive")}, {"D11-C05-P", "D11-C06-P", "D11-C07-P", "D11-C08-P"})
        self.assertEqual(len(self.validation.for_scenario("foreign_context")), 4)
        self.assertEqual(len(self.validation.for_scenario("minimum_or_missing")), 4)
        self.assertEqual(len(self.validation.for_scenario("conflict_or_ambiguity")), 4)

    def test_artifact_kind_inventory_is_closed(self) -> None:
        self.assertEqual({item.kind for item in self.artifacts.artifacts}, set(CausalBetaFrontierArtifactKind))
        self.assertEqual(self.artifacts.required_count, 16)
        self.assertEqual(self.artifacts.resolved_count, 16)
        for kind in CausalBetaFrontierArtifactKind:
            self.assertEqual(len(self.artifacts.for_kind(kind)), 1)

    def test_release_addresses_reference_the_bundle_planes(self) -> None:
        addresses = {self.bundle.fixture_address, self.bundle.evaluation_address, self.bundle.metrics_address, self.bundle.contracts_address, self.bundle.schema_address, self.bundle.lineage_address, self.bundle.provenance_address, self.bundle.depth_address, self.bundle.reconciliation_address, self.bundle.policy_address, self.bundle.review_address, self.bundle.quality_gate_address, self.bundle.scenario_address, self.bundle.validation_address}
        self.assertEqual(len(addresses), 14)
        self.assertEqual(self.release.bundle_address, self.bundle.content_address)
        self.assertEqual(self.release.gate_address, self.gate.content_address)
        self.assertEqual(self.release.depth_address, self.depth.content_address)
        self.assertEqual(self.release.review_address, self.review.content_address)

    def test_policy_rules_are_specific_to_all_operation_states(self) -> None:
        self.assertEqual(len(self.policy.rules), 16)
        self.assertEqual(len({item.rule_id for item in self.policy.rules}), 16)
        for rule in self.policy.rules:
            self.assertTrue(rule.operation)
            self.assertTrue(rule.state)
            self.assertTrue(rule.rationale)
            self.assertTrue(rule.content_address.startswith("sha256:"))

    def test_policy_decisions_align_one_to_one_with_review_items(self) -> None:
        decision_ids = {item.record_id for item in self.decisions}
        review_ids = {item.record_id for item in self.review.items}
        self.assertEqual(decision_ids, review_ids)
        self.assertEqual(len(decision_ids), 16)
        self.assertEqual(sum(item.publishable for item in self.decisions), 4)
        self.assertTrue(all(item.requires_human_review == (item.decision.value in {"review", "abstain"}) for item in self.decisions))

    def test_data_audit_detects_missing_foreign_control(self) -> None:
        record = next(item for item in self.fixture.records if item.context_key == self.fixture.foreign_context_key)
        replacement = replace(record, context_key=CAUSAL_BETA_FRONTIER_CONTEXT_KEY, content_address="")
        changed = replace(self.fixture, records=tuple(replacement if item.record_id == record.record_id else item for item in self.fixture.records), content_address="")
        audit = audit_causal_beta_frontier_data(changed)
        self.assertFalse(audit.accepted)
        self.assertIn("foreign_controls", audit.failed_checks)

    def test_schema_detects_misaligned_evaluation(self) -> None:
        evaluation = replace(self.evaluation, rows=self.evaluation.rows[:-1], content_address="")
        schema = validate_causal_beta_frontier_schema(self.fixture, evaluation)
        self.assertFalse(schema.accepted)
        self.assertIn("evaluation_rows", schema.failed_checks)

    def test_evaluation_detects_changed_expected_state(self) -> None:
        record = self.fixture.records[0]
        changed_record = replace(record, expected_state=CausalBetaState.PARTIAL, content_address="")
        changed_fixture = replace(self.fixture, records=(changed_record,) + self.fixture.records[1:], content_address="")
        evaluation = evaluate_causal_beta_frontier_fixture(changed_fixture)
        self.assertFalse(evaluation.accepted)
        self.assertIn(record.record_id, evaluation.failed_record_ids)
        self.assertEqual(evaluation.state_match_count, 15)

    def test_integrity_detects_unaccepted_provenance(self) -> None:
        provenance = replace(self.provenance, accepted=False, content_address="")
        integrity = evaluate_causal_beta_frontier_integrity(self.fixture, self.evaluation, self.lineage, provenance)
        self.assertFalse(integrity.accepted)
        self.assertIn("provenance-accepted", integrity.failed_check_ids)
        self.assertFalse(provenance.accepted)

    def test_depth_detects_unaccepted_adapter_registry(self) -> None:
        adapters = replace(self.adapters, accepted=False, content_address="")
        depth = audit_causal_beta_frontier_depth(self.fixture, self.evaluation, adapters, self.contracts, self.schema, self.metrics, self.lineage, self.provenance)
        self.assertFalse(depth.accepted)
        self.assertIn("adapter-closure", depth.failed_check_ids)

    def test_quality_gate_reports_evaluation_failure(self) -> None:
        evaluation = replace(self.evaluation, accepted=False, content_address="")
        gate = evaluate_causal_beta_frontier_quality(self.fixture, evaluation, self.contracts, self.schema, self.metrics, self.lineage, self.reconciliation, self.depth, self.review, self.decisions)
        self.assertFalse(gate.accepted)
        self.assertIn("evaluation", gate.blocking_check_ids)
        self.assertGreaterEqual(gate.failed_count, 1)

    def test_observability_records_completed_and_failed_events(self) -> None:
        ok_value, ok_event = record_causal_beta_frontier_event("depth-test", 1, "ok", lambda: self.fixture, "valid stage")
        failed_value, failed_event = record_causal_beta_frontier_event("depth-test", 2, "failed", lambda: (_ for _ in ()).throw(ValueError("expected failure")), "invalid stage")
        report = build_causal_beta_frontier_observability("depth-test", (ok_event, failed_event))
        self.assertIs(ok_value, self.fixture)
        self.assertIsNone(failed_value)
        self.assertEqual(ok_event.state, "completed")
        self.assertEqual(failed_event.state, "failed")
        self.assertEqual(report.completed_count, 1)
        self.assertEqual(report.failed_count, 1)
        self.assertFalse(report.accepted)

    def test_runtime_repeats_are_address_stable(self) -> None:
        first = run_causal_beta_frontier_runtime(run_id="depth-repeat")
        second = run_causal_beta_frontier_runtime(run_id="depth-repeat")
        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(first.evaluation.content_address, second.evaluation.content_address)
        self.assertEqual(first.metrics.content_address, second.metrics.content_address)
        self.assertEqual(first.bundle.content_address, second.bundle.content_address)
        self.assertEqual(first.assurance.content_address, second.assurance.content_address)

    def test_runtime_exposes_all_release_planes_directly(self) -> None:
        runtime = run_causal_beta_frontier_runtime(run_id="depth-surface")
        for name in ("fixture", "evaluation", "contracts", "schema", "metrics", "lineage", "provenance", "depth", "policy", "reconciliation", "review", "scenario", "validation", "gate", "bundle", "release", "artifacts", "integrity", "operational", "boundary", "replay", "review_view", "exports", "assurance"):
            self.assertTrue(hasattr(runtime, name), name)
            self.assertTrue(getattr(runtime, name))

    def test_positive_rows_are_the_only_publishable_policy_rows(self) -> None:
        for decision in self.decisions:
            if decision.publishable:
                self.assertEqual(decision.role, CausalBetaFrontierRole.POSITIVE.value)
                self.assertEqual(decision.state, "supported")
            else:
                self.assertNotEqual(decision.record_id, "")


if __name__ == "__main__":
    unittest.main()
