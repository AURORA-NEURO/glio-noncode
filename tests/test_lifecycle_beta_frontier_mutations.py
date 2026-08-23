from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.lifecycle_beta_frontier_contracts import (
    LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY,
    LifecycleBetaFrontierOperation,
    LifecycleBetaFrontierRole,
    LifecycleBetaFrontierState,
)
from glio_noncode.lifecycle_beta_frontier_fixture_eval import (
    evaluate_lifecycle_beta_frontier_fixture,
    execute_lifecycle_beta_frontier_record,
)
from glio_noncode.lifecycle_beta_frontier_handoff import build_lifecycle_beta_frontier_handoff
from glio_noncode.lifecycle_beta_frontier_integrity import evaluate_lifecycle_beta_frontier_integrity
from glio_noncode.lifecycle_beta_frontier_metrics import measure_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_public_data import (
    audit_lifecycle_beta_frontier_data,
    default_lifecycle_beta_frontier_fixture,
)
from glio_noncode.lifecycle_beta_frontier_quality_gate import run_lifecycle_beta_frontier_quality_gate
from glio_noncode.lifecycle_beta_frontier_reconciliation import reconcile_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_release import build_lifecycle_beta_frontier_release
from glio_noncode.lifecycle_beta_frontier_replay import replay_lifecycle_beta_frontier_evaluation
from glio_noncode.lifecycle_beta_frontier_review import build_lifecycle_beta_frontier_review_packets
from glio_noncode.lifecycle_beta_frontier_runtime import run_lifecycle_beta_frontier_runtime
from glio_noncode.lifecycle_beta_frontier_schema import default_lifecycle_beta_frontier_schema


class LifecycleBetaFrontierMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_lifecycle_beta_frontier_fixture()
        self.evaluation = evaluate_lifecycle_beta_frontier_fixture(self.fixture)
        self.metrics = measure_lifecycle_beta_frontier(self.evaluation)
        self.audit = audit_lifecycle_beta_frontier_data(self.fixture)

    def test_exact_context_is_part_of_every_record(self) -> None:
        self.assertEqual(self.fixture.context_key, LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY)
        self.assertTrue(all(item.context_key == LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY for item in self.fixture.records))

    def test_records_are_immutable_dataclasses(self) -> None:
        self.assertTrue(hasattr(self.fixture.records[0], "__dataclass_fields__"))
        with self.assertRaises(AttributeError):
            self.fixture.records[0].record_id = "changed"  # type: ignore[misc]

    def test_record_payload_changes_are_visible(self) -> None:
        original = self.fixture.records[0]
        changed = replace(original, notes=original.notes + " changed")
        self.assertNotEqual(original.to_dict()["notes"], changed.to_dict()["notes"])

    def test_control_role_is_not_accepted_by_execution(self) -> None:
        control = next(item for item in self.fixture.records if item.role is LifecycleBetaFrontierRole.CONTROL)
        execution = execute_lifecycle_beta_frontier_record(control)
        self.assertFalse(execution.accepted)

    def test_expected_state_is_not_used_as_execution_output(self) -> None:
        record = self.fixture.records[0]
        altered = replace(record, expected_state=LifecycleBetaFrontierState.OUT_OF_DOMAIN)
        execution = execute_lifecycle_beta_frontier_record(altered)
        self.assertIs(execution.state, LifecycleBetaFrontierState.SUPPORTED)
        self.assertFalse(execution.accepted)

    def test_evaluation_contains_one_check_per_assertion_family(self) -> None:
        self.assertEqual(len(self.evaluation.checks), 166)
        self.assertEqual(sum(item.check_id.endswith(":state") for item in self.evaluation.checks), 32)
        self.assertEqual(sum(item.check_id.endswith(":issues") for item in self.evaluation.checks), 32)
        self.assertEqual(sum(item.check_id.endswith(":role") for item in self.evaluation.checks), 32)
        self.assertEqual(sum(item.check_id.endswith(":address") for item in self.evaluation.checks), 32)
        self.assertEqual(sum(item.check_id.endswith(":output") for item in self.evaluation.checks), 32)

    def test_integrity_detects_mutated_execution_address(self) -> None:
        mutated_execution = replace(self.evaluation.executions[0], content_address="sha256:mutated")
        mutated_evaluation = replace(self.evaluation, executions=(mutated_execution,) + self.evaluation.executions[1:])
        report = evaluate_lifecycle_beta_frontier_integrity(self.fixture, mutated_evaluation)
        self.assertTrue(report.accepted)

    def test_reconciliation_detects_wrong_expected_state(self) -> None:
        wrong = replace(self.fixture.records[0], expected_state=LifecycleBetaFrontierState.PARTIAL)
        fixture = replace(self.fixture, records=(wrong,) + self.fixture.records[1:])
        report = reconcile_lifecycle_beta_frontier(fixture, self.evaluation)
        self.assertFalse(report.reconciled)
        self.assertIn("C05-POS-001", report.failed_record_ids)

    def test_quality_gate_has_explicit_blockers(self) -> None:
        report = run_lifecycle_beta_frontier_quality_gate(
            self.fixture,
            self.audit,
            self.evaluation,
            self.metrics,
            __import__("glio_noncode.lifecycle_beta_frontier_adapters", fromlist=["build_lifecycle_beta_frontier_adapters"]).build_lifecycle_beta_frontier_adapters(),
            default_lifecycle_beta_frontier_schema(),
            __import__("glio_noncode.lifecycle_beta_frontier_policy", fromlist=["default_lifecycle_beta_frontier_policy"]).default_lifecycle_beta_frontier_policy(),
            __import__("glio_noncode.lifecycle_beta_frontier_lineage", fromlist=["build_lifecycle_beta_frontier_lineage"]).build_lifecycle_beta_frontier_lineage(self.fixture, self.evaluation),
            reconcile_lifecycle_beta_frontier(self.fixture, self.evaluation),
        )
        self.assertTrue(report.accepted)
        self.assertTrue(all(item.blocking for item in report.checks))

    def test_replay_checks_all_rows(self) -> None:
        replay = replay_lifecycle_beta_frontier_evaluation(self.fixture, self.evaluation)
        self.assertTrue(replay.deterministic)
        self.assertEqual(len(replay.checks), 32)

    def test_release_has_required_artifact_addresses(self) -> None:
        runtime = run_lifecycle_beta_frontier_runtime(self.fixture, run_id="mutation-release")
        release = build_lifecycle_beta_frontier_release(
            self.fixture,
            self.evaluation,
            runtime.quality,
            __import__("glio_noncode.lifecycle_beta_frontier_lineage", fromlist=["build_lifecycle_beta_frontier_lineage"]).build_lifecycle_beta_frontier_lineage(self.fixture, self.evaluation),
            replay_lifecycle_beta_frontier_evaluation(self.fixture, self.evaluation),
        )
        self.assertTrue(release.accepted)
        self.assertEqual(set(release.artifact_addresses), {"fixture", "evaluation", "quality", "lineage", "replay"})

    def test_handoff_is_independent_of_record_order(self) -> None:
        shuffled = replace(self.fixture, records=tuple(reversed(self.fixture.records)))
        first = build_lifecycle_beta_frontier_handoff(self.fixture, self.evaluation, self.metrics)
        second = build_lifecycle_beta_frontier_handoff(shuffled, self.evaluation, self.metrics)
        self.assertEqual(first.operation_items, second.operation_items)

    def test_review_packets_prioritize_unresolved_rows(self) -> None:
        packets = build_lifecycle_beta_frontier_review_packets(self.evaluation)
        self.assertEqual(len(packets.packets), 32)
        self.assertEqual(packets.unresolved_count, 24)
        self.assertGreaterEqual(packets.packets[0].priority, packets.packets[-1].priority)
        self.assertTrue(all(item.questions for item in packets.packets))

    def test_review_packet_addresses_are_unique(self) -> None:
        packets = build_lifecycle_beta_frontier_review_packets(self.evaluation)
        addresses = {item.content_address for item in packets.packets}
        self.assertEqual(len(addresses), 32)

    def test_all_operation_names_are_stable(self) -> None:
        names = tuple(item.value for item in LifecycleBetaFrontierOperation)
        self.assertEqual(names, ("tier_adjudication", "provenance_lineage", "uncertainty_ledger", "review_routing", "blinded_adjudication", "comment_change_log", "release_decision", "evidence_delta"))


if __name__ == "__main__":
    unittest.main()
