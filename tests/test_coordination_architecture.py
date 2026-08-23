"""Comprehensive D16 coordination architecture tests."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.coordination_architecture_access import build_coordination_access_manifest
from glio_noncode.coordination_architecture_contracts import (
    COORDINATION_CASE_COUNT,
    CoordinationScenario,
    CoordinationState,
)
from glio_noncode.coordination_architecture_depth import audit_coordination_depth
from glio_noncode.coordination_architecture_deployment import (
    audit_coordination_deployment,
    build_coordination_assignments,
    build_coordination_deployment_artifacts,
)
from glio_noncode.coordination_architecture_exports import (
    coordination_quality_json,
    coordination_report_markdown,
    coordination_review_csv,
    coordination_runtime_json,
    coordination_summary,
)
from glio_noncode.coordination_architecture_failures import run_coordination_failure_injections
from glio_noncode.coordination_architecture_fallback import route_coordination_fallback
from glio_noncode.coordination_architecture_invariants import coordination_invariants
from glio_noncode.coordination_architecture_ledger import build_coordination_ledger, verify_coordination_ledger
from glio_noncode.coordination_architecture_monitoring import audit_coordination_observations, build_coordination_observations
from glio_noncode.coordination_architecture_observability import build_coordination_trace, verify_coordination_trace
from glio_noncode.coordination_architecture_operations import evaluate_coordination_fixture, execute_coordination_case
from glio_noncode.coordination_architecture_plan import audit_coordination_plan, compile_coordination_plan
from glio_noncode.coordination_architecture_policy import evaluate_coordination_policy
from glio_noncode.coordination_architecture_public_data import (
    audit_coordination_data,
    coordination_fixture_json,
    default_coordination_fixture,
)
from glio_noncode.coordination_architecture_query import query_coordination
from glio_noncode.coordination_architecture_quality import run_coordination_quality_gate
from glio_noncode.coordination_architecture_reconciliation import reconcile_coordination_evaluation
from glio_noncode.coordination_architecture_registries import (
    build_coordination_compute_registry,
    build_coordination_reference_registry,
    validate_coordination_registry,
)
from glio_noncode.coordination_architecture_release import build_coordination_release, verify_coordination_release
from glio_noncode.coordination_architecture_replay import replay_coordination_runtime
from glio_noncode.coordination_architecture_review import build_coordination_review_queue, review_queue_summary
from glio_noncode.coordination_architecture_runbook import build_coordination_runbook, runbook_is_executable
from glio_noncode.coordination_architecture_runtime import run_coordination_architecture
from glio_noncode.coordination_architecture_sandbox import execute_coordination_sandbox
from glio_noncode.coordination_architecture_schema import default_coordination_schema, validate_coordination_schema
from glio_noncode.coordination_architecture_security import evaluate_coordination_security
from glio_noncode.coordination_architecture_tools import build_coordination_tool_registry, validate_coordination_tool_registry
from glio_noncode.coordination_architecture_validation import build_coordination_validation_matrix


class CoordinationArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_coordination_fixture()
        cls.runtime = run_coordination_architecture(cls.fixture)

    def test_fixture_cardinality_and_data_audit(self) -> None:
        self.assertEqual(5, len(self.fixture.sources))
        self.assertEqual(16, len(self.fixture.operations))
        self.assertEqual(COORDINATION_CASE_COUNT, len(self.fixture.cases))
        audit = audit_coordination_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(16, len(self.fixture.positive_cases))
        self.assertEqual(48, len(self.fixture.control_cases))

    def test_fixture_json_is_parseable_and_addressed(self) -> None:
        payload = json.loads(coordination_fixture_json(self.fixture))
        self.assertEqual(self.fixture.content_address, payload["content_address"])
        self.assertEqual(64, len(payload["cases"]))
        self.assertNotIn("subject_id", json.dumps(payload))

    def test_operation_evaluation_reconciles_all_cases(self) -> None:
        evaluation = evaluate_coordination_fixture(self.fixture)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(64, evaluation.passed_cases)
        self.assertEqual(0, evaluation.failed_cases)
        self.assertEqual(16, sum(item.observed_state is CoordinationState.ACCEPTED for item in evaluation.executions if item.scenario is CoordinationScenario.POSITIVE))
        self.assertEqual(48, sum(item.observed_state is CoordinationState.REVIEW for item in evaluation.executions if item.scenario is not CoordinationScenario.POSITIVE))

    def test_plan_is_dependency_safe_and_budgeted(self) -> None:
        plan = compile_coordination_plan(self.fixture)
        self.assertTrue(plan.accepted)
        self.assertEqual(16, len(plan.nodes))
        self.assertEqual(tuple(range(1, 17)), tuple(item.ordinal for item in plan.nodes))
        self.assertEqual(168, plan.total_budget_units)
        self.assertEqual((), audit_coordination_plan(plan))

    def test_plan_detects_cycle(self) -> None:
        mutated_spec = replace(self.fixture.operations[-1], dependencies=(self.fixture.operations[-1].operation_id,))
        mutated = replace(self.fixture, operations=self.fixture.operations[:-1] + (mutated_spec,))
        plan = compile_coordination_plan(mutated)
        self.assertFalse(plan.accepted)
        self.assertIn("dependency_cycle", plan.issues)

    def test_tool_registry_is_closed(self) -> None:
        registry = build_coordination_tool_registry(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertEqual(16, len(registry.tools))
        self.assertEqual((), validate_coordination_tool_registry(registry))
        self.assertTrue(all(item.deterministic and not item.network_allowed and item.public_aggregate_only for item in registry.tools))

    def test_sandbox_and_policy_accept_positive_case(self) -> None:
        spec = self.fixture.operations[0]
        case = self.fixture.positive_cases[0]
        tool = build_coordination_tool_registry(self.fixture).tools[0]
        sandbox = execute_coordination_sandbox(case, spec, tool)
        policy = evaluate_coordination_policy(case, spec)
        self.assertIs(sandbox.state, CoordinationState.ACCEPTED)
        self.assertTrue(policy.allowed)

    def test_control_cases_are_held_by_operation_and_fallback(self) -> None:
        spec = self.fixture.operations[0]
        controls = self.fixture.control_cases[:3]
        for case in controls:
            execution = execute_coordination_case(case, spec)
            route = route_coordination_fallback(case, execution.issue_codes)
            self.assertIs(execution.observed_state, CoordinationState.REVIEW)
            self.assertIs(route.state, CoordinationState.REVIEW)
            self.assertTrue(route.selected_route)

    def test_schedule_and_review_conserve_cases(self) -> None:
        self.assertTrue(self.runtime.schedule.accepted)
        queue = build_coordination_review_queue(self.runtime.evaluation.executions)
        self.assertEqual(48, len(queue))
        summary = review_queue_summary(queue)
        self.assertEqual(48, summary["total"])
        self.assertEqual(48, summary["held"])
        self.assertEqual(48, summary["urgent"] + summary["standard"])

    def test_ledger_is_hash_chained(self) -> None:
        ledger = build_coordination_ledger(self.runtime.evaluation.executions)
        self.assertEqual(64, len(ledger.events))
        self.assertEqual((), verify_coordination_ledger(ledger))
        self.assertTrue(ledger.events[0].previous_address.startswith("coordination-genesis"))

    def test_registries_are_addressed(self) -> None:
        compute = build_coordination_compute_registry(self.fixture)
        references = build_coordination_reference_registry(self.fixture)
        self.assertTrue(compute.accepted)
        self.assertTrue(references.accepted)
        self.assertEqual((), validate_coordination_registry(compute))
        self.assertEqual((), validate_coordination_registry(references))
        self.assertEqual(5, len(references.entries))

    def test_monitoring_security_and_access_boundaries(self) -> None:
        observations = build_coordination_observations(self.fixture)
        self.assertEqual((), audit_coordination_observations(observations))
        self.assertEqual(16, len(self.runtime.security))
        self.assertTrue(all(item.state is CoordinationState.ACCEPTED for item in self.runtime.security))
        access = build_coordination_access_manifest(self.runtime)
        self.assertTrue(access.accepted)
        self.assertFalse(access.network_allowed)
        self.assertFalse(access.private_fields_allowed)

    def test_private_payload_is_reviewed_by_security(self) -> None:
        case = self.fixture.positive_cases[0]
        mutated = replace(case, payload={**case.payload, "email": "blocked"})
        decision = evaluate_coordination_security(mutated)
        self.assertIs(decision.state, CoordinationState.REVIEW)
        self.assertIn("private_key_detected", decision.reasons)

    def test_deployment_and_release_are_closed(self) -> None:
        artifacts = build_coordination_deployment_artifacts(self.fixture)
        assignments = build_coordination_assignments(self.fixture)
        self.assertEqual(5, len(artifacts))
        self.assertEqual(16, len(assignments))
        self.assertEqual((), audit_coordination_deployment(artifacts, assignments))
        release = build_coordination_release(artifacts)
        self.assertIs(release.state, CoordinationState.ACCEPTED)
        self.assertEqual((), verify_coordination_release(release))

    def test_runtime_is_twenty_stage_accepted(self) -> None:
        self.assertIs(self.runtime.state, CoordinationState.ACCEPTED)
        self.assertEqual(20, len(self.runtime.stages))
        self.assertEqual(64, len(self.runtime.ledger.events))
        self.assertEqual(5, len(self.runtime.deployment_artifacts))

    def test_quality_and_depth_are_green(self) -> None:
        quality = run_coordination_quality_gate(self.runtime)
        depth = audit_coordination_depth(self.runtime)
        self.assertTrue(quality.accepted)
        self.assertEqual(18, quality.passed_checks)
        self.assertTrue(depth.accepted)
        self.assertEqual(16, depth.passed_checks)

    def test_validation_matrix_covers_seven_planes(self) -> None:
        matrix = build_coordination_validation_matrix(self.runtime)
        self.assertTrue(matrix.accepted)
        self.assertEqual(112, len(matrix.cells))
        self.assertEqual(7, len({item.plane for item in matrix.cells}))

    def test_reconciliation_replay_and_invariants(self) -> None:
        expected = {case.case_id: (case.expected_state, case.expected_issue_codes) for case in self.fixture.cases}
        reconciliation = reconcile_coordination_evaluation(self.runtime.evaluation, expected)
        replay = replay_coordination_runtime(self.runtime)
        self.assertTrue(reconciliation.accepted)
        self.assertTrue(replay.accepted)
        self.assertEqual((), coordination_invariants(self.runtime))

    def test_runbook_trace_and_schema_are_executable(self) -> None:
        runbook = build_coordination_runbook(self.runtime)
        trace = build_coordination_trace(self.runtime)
        schema = default_coordination_schema()
        self.assertTrue(runbook_is_executable(runbook))
        self.assertEqual(20, len(runbook.steps))
        self.assertEqual((), verify_coordination_trace(trace))
        self.assertEqual(20, len(trace.events))
        self.assertEqual((), validate_coordination_schema(schema))

    def test_queries_select_stable_facets(self) -> None:
        controls = query_coordination(self.runtime, state=CoordinationState.REVIEW)
        foreign = query_coordination(self.runtime, issue_code="foreign_context")
        positive = query_coordination(self.runtime, scenario=CoordinationScenario.POSITIVE)
        self.assertEqual(48, controls.matched_count)
        self.assertEqual(16, foreign.matched_count)
        self.assertEqual(16, positive.matched_count)

    def test_exports_are_parseable(self) -> None:
        runtime_payload = json.loads(coordination_runtime_json(self.runtime))
        quality_payload = json.loads(coordination_quality_json(self.runtime))
        self.assertEqual("accepted", runtime_payload["state"])
        self.assertTrue(quality_payload["accepted"])
        self.assertEqual(49, len(coordination_review_csv(self.runtime).splitlines()))
        self.assertIn("Coordination architecture runtime", coordination_report_markdown(self.runtime))
        self.assertEqual(64, coordination_summary(self.runtime)["case_count"])

    def test_failure_controls_are_green(self) -> None:
        report = run_coordination_failure_injections()
        self.assertTrue(report.accepted)
        self.assertEqual(6, len(report.probes))
        self.assertTrue(all(item.passed for item in report.probes))


if __name__ == "__main__":
    unittest.main()
