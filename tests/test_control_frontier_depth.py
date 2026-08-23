from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.control_frontier_access import audit_control_frontier_access, build_control_frontier_access_manifest
from glio_noncode.control_frontier_audit_log import build_control_frontier_audit_log, verify_control_frontier_audit_log
from glio_noncode.control_frontier_contracts import ControlFrontierOperation, ControlFrontierState
from glio_noncode.control_frontier_fixture_eval import evaluate_control_frontier_fixture
from glio_noncode.control_frontier_integrity import evaluate_control_frontier_integrity
from glio_noncode.control_frontier_operations import run_control_frontier_operation
from glio_noncode.control_frontier_public_data import default_control_frontier_fixture
from glio_noncode.control_frontier_runtime import run_control_frontier_runtime
from glio_noncode.control_frontier_source_registry import build_control_frontier_source_registry


class ControlFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_control_frontier_fixture()
        self.evaluation = evaluate_control_frontier_fixture(self.fixture)

    def test_policy_controls_are_independently_executable(self) -> None:
        rows = self.fixture.by_operation(ControlFrontierOperation.POLICY_CLAIM_GATE)
        outputs = [run_control_frontier_operation(row.operation, row.payload) for row in rows]
        self.assertEqual(outputs[0].state, ControlFrontierState.SUPPORTED)
        self.assertEqual(outputs[1].issue_codes, ("sensitive_input",))
        self.assertEqual(outputs[2].issue_codes, ("source_allowlist_gap",))
        self.assertEqual(outputs[3].issue_codes, ("mutation_scope_denied",))

    def test_scheduler_controls_preserve_distinct_reasons(self) -> None:
        rows = self.fixture.by_operation(ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER)
        outputs = [run_control_frontier_operation(row.operation, row.payload) for row in rows]
        self.assertEqual(outputs[0].state, ControlFrontierState.READY)
        self.assertIn("capacity_exceeded", outputs[1].issue_codes)
        self.assertIn("network_limit", outputs[2].issue_codes)
        self.assertIn("dependency_cycle", outputs[3].issue_codes)

    def test_fallback_controls_do_not_select_network_or_missing_input(self) -> None:
        rows = self.fixture.by_operation(ControlFrontierOperation.DETERMINISTIC_FALLBACK)
        outputs = [run_control_frontier_operation(row.operation, row.payload) for row in rows]
        self.assertEqual(outputs[0].state, ControlFrontierState.SELECTED)
        self.assertEqual(outputs[1].state, ControlFrontierState.BLOCKED)
        self.assertEqual(outputs[2].state, ControlFrontierState.ABSTAINED)
        self.assertEqual(outputs[3].state, ControlFrontierState.ABSTAINED)

    def test_review_ledger_registry_and_monitor_paths(self) -> None:
        for operation in (ControlFrontierOperation.HUMAN_REVIEW_ROUTER, ControlFrontierOperation.EXECUTION_LEDGER, ControlFrontierOperation.MODEL_REGISTRY, ControlFrontierOperation.DATA_REFERENCE_REGISTRY, ControlFrontierOperation.DRIFT_OOD_MONITOR):
            rows = self.fixture.by_operation(operation)
            outputs = [run_control_frontier_operation(row.operation, row.payload) for row in rows]
            self.assertTrue(all(item.content_address.startswith("sha256:") for item in outputs))
            self.assertEqual(len(outputs), 4)

    def test_access_scope_mutation_is_reported(self) -> None:
        manifest = build_control_frontier_access_manifest(self.fixture)
        changed = replace(manifest, patient_level_data=True)
        self.assertIn("patient_level_data", audit_control_frontier_access(changed))

    def test_source_registry_lookup_is_stable(self) -> None:
        registry = build_control_frontier_source_registry(self.fixture)
        self.assertEqual(registry.source("src-policy").source_id, "src-policy")
        self.assertEqual(registry.source_ids, tuple(sorted(registry.source_ids)))

    def test_integrity_report_is_closed(self) -> None:
        report = evaluate_control_frontier_integrity(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 7)

    def test_runtime_replay_address_is_stable_for_same_run_inputs(self) -> None:
        first = run_control_frontier_runtime(self.fixture, run_id="depth-replay")
        second = run_control_frontier_runtime(self.fixture, run_id="depth-replay")
        self.assertEqual(first.evaluation.content_address, second.evaluation.content_address)
        self.assertEqual(first.depth.content_address, second.depth.content_address)

    def test_audit_log_mutation_is_detected(self) -> None:
        runtime = run_control_frontier_runtime(self.fixture, run_id="depth-audit")
        log = build_control_frontier_audit_log(runtime.run_id, runtime.stages)
        changed = replace(log.events[1], previous_address="sha256:changed")
        accepted, issues = verify_control_frontier_audit_log((log.events[0], changed) + log.events[2:])
        self.assertFalse(accepted)
        self.assertIn("predecessor:2", issues)


if __name__ == "__main__":
    unittest.main()
