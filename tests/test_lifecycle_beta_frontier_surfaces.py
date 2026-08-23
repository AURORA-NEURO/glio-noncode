from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.lifecycle_beta_frontier_access import (
    audit_lifecycle_beta_frontier_access,
    build_lifecycle_beta_frontier_access_manifest,
)
from glio_noncode.lifecycle_beta_frontier_audit_log import (
    build_lifecycle_beta_frontier_audit_log,
    verify_lifecycle_beta_frontier_audit_log,
)
from glio_noncode.lifecycle_beta_frontier_benchmark import run_lifecycle_beta_frontier_benchmark
from glio_noncode.lifecycle_beta_frontier_evidence_matrix import (
    LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES,
    build_lifecycle_beta_frontier_evidence_matrix,
)
from glio_noncode.lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_public_data import default_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_runtime import run_lifecycle_beta_frontier_runtime


class LifecycleBetaFrontierSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_lifecycle_beta_frontier_fixture()
        self.evaluation = evaluate_lifecycle_beta_frontier_fixture(self.fixture)

    def test_access_manifest_preserves_controls_and_boundary(self) -> None:
        manifest = build_lifecycle_beta_frontier_access_manifest(self.fixture)
        self.assertTrue(manifest.accepted)
        self.assertTrue(manifest.controls_visible)
        self.assertFalse(manifest.patient_level_data)
        self.assertEqual(len(manifest.surfaces), 6)
        self.assertEqual(audit_lifecycle_beta_frontier_access(manifest), ())

    def test_access_audit_reports_scope_mutation(self) -> None:
        manifest = build_lifecycle_beta_frontier_access_manifest(self.fixture)
        changed = replace(manifest, patient_level_data=True)
        self.assertIn("patient-level-data", audit_lifecycle_beta_frontier_access(changed))

    def test_evidence_matrix_has_six_planes_for_every_row(self) -> None:
        matrix = build_lifecycle_beta_frontier_evidence_matrix(self.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.cells), 32 * len(LIFECYCLE_BETA_FRONTIER_EVIDENCE_PLANES))
        self.assertEqual(len(matrix.cells_for(self.evaluation.executions[0].record_id)), 6)

    def test_audit_log_is_hash_linked(self) -> None:
        runtime = run_lifecycle_beta_frontier_runtime(self.fixture, run_id="surface-audit")
        log = build_lifecycle_beta_frontier_audit_log(runtime.run_id, runtime.stages)
        accepted, issues = verify_lifecycle_beta_frontier_audit_log(log.events)
        self.assertTrue(log.accepted)
        self.assertTrue(accepted)
        self.assertEqual(issues, ())
        self.assertEqual(len(log.events), 25)

    def test_benchmark_returns_two_positive_samples(self) -> None:
        report = run_lifecycle_beta_frontier_benchmark(self.fixture, repetitions=1)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.samples), 2)
        self.assertGreater(report.slowest_records_per_second, 0)

    def test_audit_log_detects_link_mutation(self) -> None:
        runtime = run_lifecycle_beta_frontier_runtime(self.fixture, run_id="surface-mutation")
        log = build_lifecycle_beta_frontier_audit_log(runtime.run_id, runtime.stages)
        changed = replace(log.events[1], previous_address="sha256:changed")
        accepted, issues = verify_lifecycle_beta_frontier_audit_log((log.events[0], changed) + log.events[2:])
        self.assertFalse(accepted)
        self.assertIn("predecessor:2", issues)


if __name__ == "__main__":
    unittest.main()
