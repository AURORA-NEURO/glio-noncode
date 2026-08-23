from __future__ import annotations

import unittest

from glio_noncode.validation_release_frontier_access import audit_validation_release_access, build_validation_release_access_manifest
from glio_noncode.validation_release_frontier_adapters import build_validation_release_adapters
from glio_noncode.validation_release_frontier_assurance import build_validation_release_assurance_summary
from glio_noncode.validation_release_frontier_artifacts import build_validation_release_artifact_inventory
from glio_noncode.validation_release_frontier_compatibility import evaluate_validation_release_compatibility
from glio_noncode.validation_release_frontier_compliance import evaluate_validation_release_compliance
from glio_noncode.validation_release_frontier_controls import build_validation_release_control_coverage
from glio_noncode.validation_release_frontier_depth import audit_validation_release_depth
from glio_noncode.validation_release_frontier_diagnostics import diagnose_validation_release
from glio_noncode.validation_release_frontier_evidence_matrix import build_validation_release_evidence_matrix
from glio_noncode.validation_release_frontier_execution_plan import build_validation_release_execution_plan, validate_validation_release_execution_plan
from glio_noncode.validation_release_frontier_failure_injection import run_validation_release_failure_injections
from glio_noncode.validation_release_frontier_fixture_eval import evaluate_validation_release_fixture
from glio_noncode.validation_release_frontier_freshness import evaluate_validation_release_freshness
from glio_noncode.validation_release_frontier_handoff import build_validation_release_handoff
from glio_noncode.validation_release_frontier_integrity import evaluate_validation_release_integrity
from glio_noncode.validation_release_frontier_invariants import assert_validation_release_invariants, evaluate_validation_release_invariants
from glio_noncode.validation_release_frontier_lineage import build_validation_release_lineage, verify_validation_release_lineage
from glio_noncode.validation_release_frontier_metrics import measure_validation_release
from glio_noncode.validation_release_frontier_operational import build_validation_release_operational_matrix
from glio_noncode.validation_release_frontier_package import build_validation_release_package_manifest
from glio_noncode.validation_release_frontier_performance import build_validation_release_performance_budget
from glio_noncode.validation_release_frontier_policy import default_validation_release_policy
from glio_noncode.validation_release_frontier_provenance import build_validation_release_provenance
from glio_noncode.validation_release_frontier_public_data import audit_validation_release_frontier_data, default_validation_release_frontier_fixture
from glio_noncode.validation_release_frontier_quality_gate import run_validation_release_quality_gate
from glio_noncode.validation_release_frontier_query import query_validation_release
from glio_noncode.validation_release_frontier_reconciliation import reconcile_validation_release
from glio_noncode.validation_release_frontier_recovery import build_validation_release_recovery_plan
from glio_noncode.validation_release_frontier_release import build_validation_release_manifest
from glio_noncode.validation_release_frontier_release_checks import evaluate_validation_release_checks
from glio_noncode.validation_release_frontier_replay import replay_validation_release_evaluation
from glio_noncode.validation_release_frontier_review_queue import build_validation_release_review_queue
from glio_noncode.validation_release_frontier_review_sla import build_validation_release_review_sla
from glio_noncode.validation_release_frontier_run_manifest import build_validation_release_run_manifest
from glio_noncode.validation_release_frontier_runbook import build_validation_release_runbook, runbook_is_executable
from glio_noncode.validation_release_frontier_runtime import run_validation_release_runtime
from glio_noncode.validation_release_frontier_scenario_matrix import evaluate_validation_release_scenarios
from glio_noncode.validation_release_frontier_schema import default_validation_release_frontier_schema
from glio_noncode.validation_release_frontier_source_registry import build_validation_release_source_registry
from glio_noncode.validation_release_frontier_validation_matrix import build_validation_release_validation_matrix
from glio_noncode.validation_release_frontier_evidence_matrix import build_validation_release_evidence_matrix


class ValidationReleaseFrontierDepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_validation_release_frontier_fixture()
        cls.evaluation = evaluate_validation_release_fixture(cls.fixture)
        cls.metrics = measure_validation_release(cls.evaluation)
        cls.adapters = build_validation_release_adapters()
        cls.schema = default_validation_release_frontier_schema()
        cls.audit = audit_validation_release_frontier_data(cls.fixture)
        cls.lineage = build_validation_release_lineage(cls.fixture, cls.evaluation)
        cls.reconciliation = reconcile_validation_release(cls.fixture, cls.evaluation)
        cls.quality = run_validation_release_quality_gate(cls.audit, cls.evaluation, cls.adapters, cls.schema, cls.reconciliation)
        cls.replay = replay_validation_release_evaluation(cls.fixture, cls.evaluation)
        cls.release = build_validation_release_manifest(cls.fixture, cls.evaluation, cls.quality, cls.lineage, cls.replay)
        cls.artifacts = build_validation_release_artifact_inventory(cls.fixture, cls.release)
        cls.queue = build_validation_release_review_queue(cls.evaluation)

    def test_runtime_depth(self) -> None:
        runtime = run_validation_release_runtime(self.fixture, run_id="depth-runtime")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 50)
        self.assertEqual(tuple(item.sequence for item in runtime.stages), tuple(range(1, 51)))
        self.assertEqual(len(runtime.evaluation.checks), 80)

    def test_matrices_and_controls(self) -> None:
        self.assertTrue(evaluate_validation_release_scenarios(self.evaluation).accepted)
        self.assertEqual(evaluate_validation_release_scenarios(self.evaluation).cell_count, 16)
        self.assertTrue(build_validation_release_control_coverage(self.evaluation).accepted)
        self.assertEqual(build_validation_release_validation_matrix(self.evaluation).cell_count, 96)
        self.assertEqual(len(build_validation_release_evidence_matrix(self.fixture, self.evaluation).cells), 96)
        self.assertTrue(audit_validation_release_depth(self.fixture, self.evaluation).accepted)

    def test_release_integrity_and_review(self) -> None:
        integrity = evaluate_validation_release_integrity(self.fixture, self.evaluation)
        self.assertTrue(integrity.accepted)
        self.assertEqual(verify_validation_release_lineage(self.lineage), ())
        self.assertTrue(self.release.accepted)
        self.assertTrue(self.artifacts.complete)
        self.assertTrue(build_validation_release_package_manifest(self.release, self.artifacts).complete)
        self.assertTrue(evaluate_validation_release_checks(self.quality, integrity, evaluate_validation_release_compatibility()).passed)
        self.assertTrue(self.queue.accepted)
        self.assertTrue(build_validation_release_review_sla(self.queue).accepted)

    def test_operations_and_recovery(self) -> None:
        self.assertTrue(build_validation_release_operational_matrix(self.evaluation).accepted)
        self.assertTrue(evaluate_validation_release_compliance(self.fixture).accepted)
        self.assertTrue(diagnose_validation_release(self.evaluation).accepted)
        self.assertTrue(run_validation_release_failure_injections().accepted)
        self.assertTrue(build_validation_release_recovery_plan(self.evaluation).accepted)
        self.assertTrue(build_validation_release_performance_budget(self.evaluation).accepted)
        self.assertEqual(run_validation_release_runtime(self.fixture, run_id="threshold-runtime").thresholds.probe_count, 4)
        self.assertEqual(query_validation_release(self.evaluation, "review").hits[0].state, "review")

    def test_plan_access_and_handoff(self) -> None:
        plan = build_validation_release_execution_plan()
        self.assertEqual(validate_validation_release_execution_plan(plan), ())
        provenance = build_validation_release_provenance("depth-run", self.fixture, plan, default_validation_release_policy())
        self.assertTrue(provenance.complete)
        manifest = build_validation_release_run_manifest("depth-run", plan, provenance, ("data-audit", "release"))
        self.assertTrue(manifest.accepted)
        self.assertTrue(runbook_is_executable(build_validation_release_runbook()))
        access = build_validation_release_access_manifest(self.fixture)
        self.assertEqual(audit_validation_release_access(access), ())
        self.assertTrue(build_validation_release_handoff(self.fixture, self.evaluation, self.metrics, self.queue).accepted)
        self.assertTrue(build_validation_release_source_registry(self.fixture).accepted)
        self.assertTrue(evaluate_validation_release_freshness(self.fixture).accepted)
        invariants = evaluate_validation_release_invariants(self.fixture, self.evaluation)
        assert_validation_release_invariants(invariants)


if __name__ == "__main__":
    unittest.main()
