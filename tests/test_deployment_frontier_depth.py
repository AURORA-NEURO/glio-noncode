from __future__ import annotations

import unittest

from glio_noncode.deployment_frontier_access import audit_deployment_frontier_access, build_deployment_frontier_access_manifest
from glio_noncode.deployment_frontier_adapters import build_deployment_frontier_adapters
from glio_noncode.deployment_frontier_assurance import build_deployment_frontier_assurance_summary
from glio_noncode.deployment_frontier_artifacts import build_deployment_frontier_artifact_inventory
from glio_noncode.deployment_frontier_claim_boundary import evaluate_deployment_frontier_claim_boundary
from glio_noncode.deployment_frontier_compatibility import evaluate_deployment_frontier_compatibility
from glio_noncode.deployment_frontier_compliance import evaluate_deployment_frontier_compliance
from glio_noncode.deployment_frontier_contracts import DeploymentFrontierOperation
from glio_noncode.deployment_frontier_controls import build_deployment_frontier_control_coverage
from glio_noncode.deployment_frontier_depth import audit_deployment_frontier_depth
from glio_noncode.deployment_frontier_diagnostics import diagnose_deployment_frontier
from glio_noncode.deployment_frontier_evidence_matrix import build_deployment_frontier_evidence_matrix
from glio_noncode.deployment_frontier_execution_plan import build_deployment_frontier_execution_plan, validate_deployment_frontier_execution_plan
from glio_noncode.deployment_frontier_failure_injection import run_deployment_frontier_failure_injections
from glio_noncode.deployment_frontier_fixture_eval import evaluate_deployment_frontier_fixture
from glio_noncode.deployment_frontier_freshness import evaluate_deployment_frontier_freshness
from glio_noncode.deployment_frontier_handoff import build_deployment_frontier_handoff
from glio_noncode.deployment_frontier_integrity import evaluate_deployment_frontier_integrity
from glio_noncode.deployment_frontier_invariants import assert_deployment_frontier_invariants, evaluate_deployment_frontier_invariants
from glio_noncode.deployment_frontier_lineage import build_deployment_frontier_lineage, verify_deployment_frontier_lineage
from glio_noncode.deployment_frontier_metrics import measure_deployment_frontier
from glio_noncode.deployment_frontier_operational import build_deployment_frontier_operational_matrix
from glio_noncode.deployment_frontier_package import build_deployment_frontier_package_manifest
from glio_noncode.deployment_frontier_performance import build_deployment_frontier_performance_budget
from glio_noncode.deployment_frontier_policy import default_deployment_frontier_policy, evaluate_deployment_frontier_policy
from glio_noncode.deployment_frontier_provenance import build_deployment_frontier_provenance
from glio_noncode.deployment_frontier_public_data import audit_deployment_frontier_data, default_deployment_frontier_fixture
from glio_noncode.deployment_frontier_quality_gate import run_deployment_frontier_quality_gate
from glio_noncode.deployment_frontier_query import query_deployment_frontier
from glio_noncode.deployment_frontier_reconciliation import reconcile_deployment_frontier
from glio_noncode.deployment_frontier_recovery import build_deployment_frontier_recovery_plan
from glio_noncode.deployment_frontier_release import build_deployment_frontier_release
from glio_noncode.deployment_frontier_release_checks import evaluate_deployment_frontier_release_checks
from glio_noncode.deployment_frontier_replay import replay_deployment_frontier_evaluation
from glio_noncode.deployment_frontier_review_queue import build_deployment_frontier_review_queue
from glio_noncode.deployment_frontier_review_sla import build_deployment_frontier_review_sla
from glio_noncode.deployment_frontier_run_manifest import build_deployment_frontier_run_manifest
from glio_noncode.deployment_frontier_runbook import build_deployment_frontier_runbook, runbook_is_executable
from glio_noncode.deployment_frontier_runtime import run_deployment_frontier_runtime
from glio_noncode.deployment_frontier_scenario_matrix import evaluate_deployment_frontier_scenarios
from glio_noncode.deployment_frontier_schema import default_deployment_frontier_schema
from glio_noncode.deployment_frontier_source_registry import build_deployment_frontier_source_registry
from glio_noncode.deployment_frontier_summary import build_deployment_frontier_summary
from glio_noncode.deployment_frontier_thresholds import build_deployment_frontier_threshold_report
from glio_noncode.deployment_frontier_transcript import build_deployment_frontier_transcript, verify_deployment_frontier_transcript
from glio_noncode.deployment_frontier_validation_matrix import build_deployment_frontier_validation_matrix
from glio_noncode.deployment_frontier_views import build_deployment_frontier_view


class DeploymentFrontierDepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_deployment_frontier_fixture()
        cls.evaluation = evaluate_deployment_frontier_fixture(cls.fixture)
        cls.metrics = measure_deployment_frontier(cls.evaluation)
        cls.adapters = build_deployment_frontier_adapters()
        cls.schema = default_deployment_frontier_schema()
        cls.lineage = build_deployment_frontier_lineage(cls.fixture, cls.evaluation)
        cls.reconciliation = reconcile_deployment_frontier(cls.fixture, cls.evaluation)
        cls.quality = run_deployment_frontier_quality_gate(audit_deployment_frontier_data(cls.fixture), cls.evaluation, cls.adapters, cls.schema, cls.reconciliation)
        cls.replay = replay_deployment_frontier_evaluation(cls.fixture, cls.evaluation)
        cls.release = build_deployment_frontier_release(cls.fixture, cls.evaluation, cls.quality, cls.lineage, cls.replay)
        cls.artifacts = build_deployment_frontier_artifact_inventory(cls.fixture, cls.release)
        cls.queue = build_deployment_frontier_review_queue(cls.evaluation)

    def test_runtime_has_deep_ordered_stages(self) -> None:
        runtime = run_deployment_frontier_runtime(self.fixture, run_id="depth-runtime")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 38)
        self.assertEqual(tuple(item.sequence for item in runtime.stages), tuple(range(1, 39)))
        self.assertEqual(len(runtime.evaluation.checks), 80)

    def test_projection_counts(self) -> None:
        self.assertTrue(evaluate_deployment_frontier_scenarios(self.evaluation).accepted)
        self.assertEqual(evaluate_deployment_frontier_scenarios(self.evaluation).cell_count, 16)
        self.assertEqual(build_deployment_frontier_threshold_report().probe_count, 4)
        self.assertEqual(build_deployment_frontier_validation_matrix(self.evaluation).cell_count, 64)
        self.assertEqual(len(build_deployment_frontier_evidence_matrix(self.evaluation).cells), 96)
        self.assertTrue(build_deployment_frontier_control_coverage(self.evaluation).accepted)
        self.assertTrue(audit_deployment_frontier_depth(self.fixture, self.evaluation).accepted)

    def test_release_and_integrity_planes(self) -> None:
        integrity = evaluate_deployment_frontier_integrity(self.fixture, self.evaluation)
        self.assertTrue(integrity.accepted)
        self.assertEqual(verify_deployment_frontier_lineage(self.lineage), ())
        self.assertTrue(self.release.accepted)
        self.assertTrue(self.artifacts.complete)
        self.assertTrue(build_deployment_frontier_package_manifest(self.release, self.artifacts).complete)
        self.assertTrue(evaluate_deployment_frontier_release_checks(self.quality, integrity, evaluate_deployment_frontier_compatibility()).passed)

    def test_review_compliance_and_operations(self) -> None:
        self.assertTrue(self.queue.accepted)
        self.assertTrue(build_deployment_frontier_review_sla(self.queue).accepted)
        self.assertTrue(build_deployment_frontier_operational_matrix(self.evaluation).accepted)
        self.assertTrue(evaluate_deployment_frontier_compliance(self.fixture).accepted)
        self.assertTrue(evaluate_deployment_frontier_claim_boundary(self.evaluation).accepted)
        self.assertTrue(diagnose_deployment_frontier(self.evaluation).accepted)
        self.assertEqual(len(query_deployment_frontier(self.evaluation, "privacy").hits), 5)

    def test_failure_recovery_and_run_manifest(self) -> None:
        failure = run_deployment_frontier_failure_injections()
        self.assertTrue(failure.accepted)
        recovery = build_deployment_frontier_recovery_plan(self.evaluation)
        self.assertTrue(recovery.accepted)
        plan = build_deployment_frontier_execution_plan()
        self.assertEqual(validate_deployment_frontier_execution_plan(plan), ())
        self.assertTrue(build_deployment_frontier_performance_budget(self.evaluation).accepted)
        provenance = build_deployment_frontier_provenance("depth-run", self.fixture, plan, default_deployment_frontier_policy())
        self.assertTrue(provenance.complete)
        manifest = build_deployment_frontier_run_manifest("depth-run", plan, provenance, ("data-audit", "release"))
        self.assertTrue(manifest.accepted)
        self.assertTrue(runbook_is_executable(build_deployment_frontier_runbook()))
        transcript = build_deployment_frontier_transcript(("data-audit", "release"))
        self.assertEqual(verify_deployment_frontier_transcript(transcript), ())
        self.assertTrue(evaluate_deployment_frontier_freshness(self.fixture).accepted)

    def test_invariants_access_and_handoff(self) -> None:
        report = evaluate_deployment_frontier_invariants(self.fixture, self.evaluation)
        assert_deployment_frontier_invariants(report)
        access = build_deployment_frontier_access_manifest(self.fixture)
        self.assertTrue(access.accepted)
        self.assertEqual(audit_deployment_frontier_access(access), ())
        handoff = build_deployment_frontier_handoff(self.fixture, self.evaluation, self.metrics, self.queue)
        self.assertTrue(handoff.accepted)
        self.assertTrue(build_deployment_frontier_source_registry(self.fixture).accepted)
        self.assertTrue(build_deployment_frontier_assurance_summary(self.quality, audit_deployment_frontier_depth(self.fixture, self.evaluation), evaluate_deployment_frontier_integrity(self.fixture, self.evaluation)).accepted)


if __name__ == "__main__":
    unittest.main()
