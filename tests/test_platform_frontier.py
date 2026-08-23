from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.platform_frontier_contracts import PlatformFrontierOperation, PlatformFrontierRole, PlatformFrontierState
from glio_noncode.platform_frontier_fixture_eval import evaluate_platform_frontier_fixture
from glio_noncode.platform_frontier_operations import run_platform_frontier_operation
from glio_noncode.platform_frontier_public_data import audit_platform_frontier_data, default_platform_frontier_fixture


class PlatformFrontierCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_platform_frontier_fixture()
        cls.audit = audit_platform_frontier_data(cls.fixture)
        cls.evaluation = evaluate_platform_frontier_fixture(cls.fixture)

    def test_fixture_has_four_operations_and_controls(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual({len(self.fixture.by_operation(item)) for item in PlatformFrontierOperation}, {4})

    def test_evaluation_has_five_checks_per_record(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 80)
        self.assertEqual(self.evaluation.passed_checks, 80)
        self.assertEqual(sum(item.accepted for item in self.evaluation.executions), 4)

    def test_each_positive_operation_is_functional(self) -> None:
        positives = [item for item in self.fixture.records if item.role is PlatformFrontierRole.POSITIVE]
        for record in positives:
            result = run_platform_frontier_operation(record.operation, record.payload)
            self.assertEqual(result.state, record.expected_state)
            self.assertEqual(result.issue_codes, ())
            self.assertTrue(result.output)

    def test_planning_controls_are_explicit(self) -> None:
        for record_id, state, issue in (
            ("C01-CTRL-001", PlatformFrontierState.ABSTAINED, "no_roles_requested"),
            ("C01-CTRL-002", PlatformFrontierState.REJECTED, "unknown_role"),
            ("C01-CTRL-003", PlatformFrontierState.REJECTED, "claim_ceiling_exceeded"),
        ):
            record = next(item for item in self.fixture.records if item.record_id == record_id)
            result = run_platform_frontier_operation(record.operation, record.payload)
            self.assertEqual(result.state, state)
            self.assertEqual(result.issue_codes, (issue,))

    def test_workflow_controls_are_explicit(self) -> None:
        for record_id, state, issue in (
            ("C02-CTRL-001", PlatformFrontierState.BLOCKED, "dependency_cycle"),
            ("C02-CTRL-002", PlatformFrontierState.BLOCKED, "missing_dependency"),
            ("C02-CTRL-003", PlatformFrontierState.PARTIAL, "network_or_nondeterminism"),
        ):
            record = next(item for item in self.fixture.records if item.record_id == record_id)
            result = run_platform_frontier_operation(record.operation, record.payload)
            self.assertEqual(result.state, state)
            self.assertEqual(result.issue_codes, (issue,))

    def test_registry_controls_are_explicit(self) -> None:
        expected = {
            "C03-CTRL-001": (PlatformFrontierState.REJECTED, ("tool_not_registered",)),
            "C03-CTRL-002": (PlatformFrontierState.INCOMPATIBLE, ("input_contract_mismatch",)),
            "C03-CTRL-003": (PlatformFrontierState.INCOMPATIBLE, ("registry_cardinality_mismatch",)),
        }
        for record in self.fixture.records:
            if record.record_id not in expected:
                continue
            result = run_platform_frontier_operation(record.operation, record.payload)
            self.assertEqual((result.state, result.issue_codes), expected[record.record_id])

    def test_sandbox_controls_are_explicit(self) -> None:
        expected = {
            "C04-CTRL-001": (PlatformFrontierState.DENIED, ("handler_not_registered",)),
            "C04-CTRL-002": (PlatformFrontierState.DENIED, ("network_egress_disabled",)),
            "C04-CTRL-003": (PlatformFrontierState.REJECTED, ("direct_identifier",)),
        }
        for record in self.fixture.records:
            if record.record_id not in expected:
                continue
            result = run_platform_frontier_operation(record.operation, record.payload)
            self.assertEqual((result.state, result.issue_codes), expected[record.record_id])

    def test_control_outputs_do_not_include_sensitive_value(self) -> None:
        record = next(item for item in self.fixture.records if item.record_id == "C04-CTRL-003")
        result = run_platform_frontier_operation(record.operation, record.payload)
        self.assertNotIn("hidden", str(result.output))
        self.assertEqual(result.issue_codes, ("direct_identifier",))

    def test_context_audit_is_closed(self) -> None:
        from glio_noncode.platform_frontier_fixture_eval import audit_platform_frontier_context

        self.assertEqual(audit_platform_frontier_context(self.fixture), ())
        changed = replace(self.fixture.records[0], context_key="foreign")
        changed_fixture = replace(self.fixture, records=(changed,) + self.fixture.records[1:])
        self.assertIn("C01-POS-001", audit_platform_frontier_context(changed_fixture))


if __name__ == "__main__":
    unittest.main()
