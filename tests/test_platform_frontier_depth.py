from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.platform_frontier_access import build_platform_frontier_access_manifest
from glio_noncode.platform_frontier_adapters import build_platform_frontier_adapters
from glio_noncode.platform_frontier_assurance import build_platform_frontier_assurance_summary
from glio_noncode.platform_frontier_audit_log import build_platform_frontier_audit_log, verify_platform_frontier_audit_log
from glio_noncode.platform_frontier_benchmark import run_platform_frontier_benchmark
from glio_noncode.platform_frontier_bundle import assemble_platform_frontier_bundle
from glio_noncode.platform_frontier_change_control import default_platform_frontier_change_control
from glio_noncode.platform_frontier_claim_boundary import evaluate_platform_frontier_claim_boundary
from glio_noncode.platform_frontier_compatibility import evaluate_platform_frontier_compatibility
from glio_noncode.platform_frontier_compliance import evaluate_platform_frontier_compliance
from glio_noncode.platform_frontier_contracts import PlatformFrontierOperation
from glio_noncode.platform_frontier_controls import build_platform_frontier_control_coverage
from glio_noncode.platform_frontier_data_dictionary import default_platform_frontier_data_dictionary
from glio_noncode.platform_frontier_delta import compare_platform_frontier_evaluations
from glio_noncode.platform_frontier_depth import audit_platform_frontier_depth
from glio_noncode.platform_frontier_diagnostics import diagnose_platform_frontier
from glio_noncode.platform_frontier_evidence_matrix import build_platform_frontier_evidence_matrix
from glio_noncode.platform_frontier_failure_injection import run_platform_frontier_failure_injections
from glio_noncode.platform_frontier_fixture_eval import evaluate_platform_frontier_fixture
from glio_noncode.platform_frontier_handoff import build_platform_frontier_handoff
from glio_noncode.platform_frontier_integrity import evaluate_platform_frontier_integrity
from glio_noncode.platform_frontier_invariants import evaluate_platform_frontier_invariants
from glio_noncode.platform_frontier_lineage import build_platform_frontier_lineage, verify_platform_frontier_lineage
from glio_noncode.platform_frontier_metrics import measure_platform_frontier
from glio_noncode.platform_frontier_operations import run_platform_frontier_operation
from glio_noncode.platform_frontier_operational import build_platform_frontier_operational_matrix
from glio_noncode.platform_frontier_package import build_platform_frontier_package_manifest
from glio_noncode.platform_frontier_partition import build_platform_frontier_partitions
from glio_noncode.platform_frontier_performance import build_platform_frontier_performance_budget
from glio_noncode.platform_frontier_policy import default_platform_frontier_policy, evaluate_platform_frontier_policy
from glio_noncode.platform_frontier_public_data import default_platform_frontier_fixture
from glio_noncode.platform_frontier_quality_gate import run_platform_frontier_quality_gate
from glio_noncode.platform_frontier_query import PlatformFrontierQuery, query_platform_frontier_evaluation
from glio_noncode.platform_frontier_reconciliation import reconcile_platform_frontier
from glio_noncode.platform_frontier_recovery import build_platform_frontier_recovery_plan
from glio_noncode.platform_frontier_release import build_platform_frontier_release
from glio_noncode.platform_frontier_release_checks import evaluate_platform_frontier_release_checks
from glio_noncode.platform_frontier_replay import replay_platform_frontier_evaluation
from glio_noncode.platform_frontier_review_queue import build_platform_frontier_review_queue
from glio_noncode.platform_frontier_review_sla import build_platform_frontier_review_sla
from glio_noncode.platform_frontier_runbook import build_platform_frontier_runbook
from glio_noncode.platform_frontier_runtime import run_platform_frontier_runtime
from glio_noncode.platform_frontier_scenario_matrix import evaluate_platform_frontier_scenarios
from glio_noncode.platform_frontier_schema import default_platform_frontier_schema, validate_platform_frontier_schema
from glio_noncode.platform_frontier_source_registry import build_platform_frontier_source_registry
from glio_noncode.platform_frontier_support import default_platform_frontier_support_directory
from glio_noncode.platform_frontier_thresholds import build_platform_frontier_threshold_report
from glio_noncode.platform_frontier_transcript import build_platform_frontier_transcript, verify_platform_frontier_transcript
from glio_noncode.platform_frontier_validation_matrix import build_platform_frontier_validation_matrix
from glio_noncode.platform_frontier_versioning import inspect_platform_frontier_version, migrate_platform_frontier_metadata
from glio_noncode.platform_frontier_views import build_platform_frontier_view
from glio_noncode.serialization import jsonable


class PlatformFrontierDepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_platform_frontier_fixture()
        cls.evaluation = evaluate_platform_frontier_fixture(cls.fixture)
        cls.audit = __import__("glio_noncode.platform_frontier_public_data", fromlist=["audit_platform_frontier_data"]).audit_platform_frontier_data(cls.fixture)
        cls.adapters = build_platform_frontier_adapters()
        cls.schema = default_platform_frontier_schema()
        cls.policy = default_platform_frontier_policy()
        cls.metrics = measure_platform_frontier(cls.evaluation)
        cls.lineage = build_platform_frontier_lineage(cls.fixture, cls.evaluation)
        cls.reconciliation = reconcile_platform_frontier(cls.fixture, cls.evaluation)
        cls.quality = run_platform_frontier_quality_gate(cls.fixture, cls.audit, cls.evaluation, cls.metrics, cls.adapters, cls.schema, cls.policy, cls.lineage, cls.reconciliation)
        cls.replay = replay_platform_frontier_evaluation(cls.fixture, cls.evaluation)
        cls.release = build_platform_frontier_release(cls.fixture, cls.evaluation, cls.quality, cls.lineage, cls.replay)
        cls.artifacts = __import__("glio_noncode.platform_frontier_artifacts", fromlist=["build_platform_frontier_artifact_inventory"]).build_platform_frontier_artifact_inventory(cls.fixture, cls.release)
        cls.runtime = run_platform_frontier_runtime(cls.fixture, run_id="platform-depth-test")

    def test_depth_counts(self) -> None:
        depth = audit_platform_frontier_depth(self.fixture, self.evaluation)
        self.assertTrue(depth.accepted)
        self.assertEqual(len(depth.checks), 8)
        self.assertEqual(build_platform_frontier_threshold_report().probe_count, 16)
        self.assertEqual(build_platform_frontier_validation_matrix(self.evaluation).cell_count, 64)
        self.assertEqual(len(build_platform_frontier_evidence_matrix(self.evaluation).cells), 96)

    def test_runtime_closes_twenty_four_stages(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 24)
        self.assertEqual(self.runtime.stage_ids[0], "data-audit")
        self.assertEqual(self.runtime.stage_ids[-1], "package-close")

    def test_integrity_invariants_and_claims(self) -> None:
        self.assertTrue(evaluate_platform_frontier_integrity(self.fixture, self.evaluation).accepted)
        self.assertTrue(evaluate_platform_frontier_invariants(self.fixture, self.evaluation).accepted)
        self.assertTrue(evaluate_platform_frontier_claim_boundary(self.evaluation).accepted)
        self.assertTrue(evaluate_platform_frontier_compliance(self.fixture, self.evaluation, self.policy).accepted)

    def test_operational_surfaces_close(self) -> None:
        queue = build_platform_frontier_review_queue(self.evaluation)
        self.assertTrue(build_platform_frontier_control_coverage(self.evaluation).accepted)
        self.assertTrue(build_platform_frontier_operational_matrix(self.evaluation).accepted)
        self.assertTrue(build_platform_frontier_review_sla(queue).accepted)
        self.assertTrue(build_platform_frontier_handoff(self.fixture, self.evaluation, self.metrics, queue).accepted)
        self.assertTrue(build_platform_frontier_source_registry(self.fixture).accepted)
        self.assertTrue(default_platform_frontier_support_directory().accepted)
        self.assertTrue(build_platform_frontier_runbook().accepted)
        self.assertTrue(build_platform_frontier_recovery_plan().accepted)
        self.assertTrue(default_platform_frontier_change_control().accepted)

    def test_projection_and_query_surfaces(self) -> None:
        view = build_platform_frontier_view(self.evaluation)
        self.assertTrue(view.accepted)
        self.assertEqual(query_platform_frontier_evaluation(self.evaluation, PlatformFrontierQuery(operation=PlatformFrontierOperation.WORKFLOW_COMPILER)).total_matches, 4)
        self.assertTrue(build_platform_frontier_partitions(self.evaluation).accepted)
        self.assertTrue(compare_platform_frontier_evaluations(self.evaluation, self.evaluation).accepted)
        self.assertTrue(diagnose_platform_frontier(self.evaluation).accepted)

    def test_release_and_bundle_surfaces_close(self) -> None:
        summary = __import__("glio_noncode.platform_frontier_summary", fromlist=["build_platform_frontier_summary"]).build_platform_frontier_summary(self.evaluation, self.metrics, self.release)
        package = build_platform_frontier_package_manifest(self.release, self.artifacts)
        bundle = assemble_platform_frontier_bundle(self.release, package, self.artifacts, summary)
        self.assertTrue(self.release.accepted)
        self.assertTrue(package.complete)
        self.assertTrue(bundle.accepted)
        self.assertTrue(build_platform_frontier_assurance_summary(self.evaluation, audit_platform_frontier_depth(self.fixture, self.evaluation), evaluate_platform_frontier_integrity(self.fixture, self.evaluation)).accepted)

    def test_access_version_and_compatibility(self) -> None:
        self.assertTrue(build_platform_frontier_access_manifest(self.fixture).accepted)
        receipt = inspect_platform_frontier_version(jsonable(self.fixture))
        self.assertTrue(receipt.compatible)
        self.assertTrue(migrate_platform_frontier_metadata({"fixture_id": self.fixture.fixture_id, "fixture_version": "old"})["migration_receipt"].startswith("sha256:"))
        self.assertTrue(evaluate_platform_frontier_compatibility(self.fixture.fixture_version, self.adapters, self.schema).compatible)
        self.assertEqual(validate_platform_frontier_schema(self.schema), ())

    def test_failure_probes_and_transcript(self) -> None:
        self.assertTrue(run_platform_frontier_failure_injections(self.fixture).accepted)
        rows = tuple({"stage_id": item.stage_id, "output_address": item.output_address, "detail": item.detail} for item in self.runtime.stages)
        transcript = build_platform_frontier_transcript(self.runtime.run_id, rows)
        self.assertTrue(transcript.accepted)
        self.assertEqual(verify_platform_frontier_transcript(transcript), ())
        self.assertTrue(run_platform_frontier_benchmark(self.fixture, repetitions=1).accepted)

    def test_audit_log_and_access_are_addressed(self) -> None:
        log = build_platform_frontier_audit_log("platform-test", ({"event_id": "one", "kind": "start", "payload_address": "sha256:one"}, {"event_id": "two", "kind": "close", "payload_address": "sha256:two"}))
        self.assertTrue(log.accepted)
        self.assertEqual(verify_platform_frontier_audit_log(log), ())
        self.assertEqual(len(build_platform_frontier_access_manifest(self.fixture).surfaces), 6)


if __name__ == "__main__":
    unittest.main()
