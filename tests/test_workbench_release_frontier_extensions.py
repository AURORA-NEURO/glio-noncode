from __future__ import annotations

import unittest

from glio_noncode.workbench_release_frontier_access import build_workbench_release_access_manifest
from glio_noncode.workbench_release_frontier_controls import build_workbench_release_control_coverage
from glio_noncode.workbench_release_frontier_depth import audit_workbench_release_depth
from glio_noncode.workbench_release_frontier_evidence_matrix import build_workbench_release_evidence_matrix
from glio_noncode.workbench_release_frontier_failure_injection import run_workbench_release_failure_injections
from glio_noncode.workbench_release_frontier_fixture_eval import evaluate_workbench_release_fixture
from glio_noncode.workbench_release_frontier_integrity import evaluate_workbench_release_integrity
from glio_noncode.workbench_release_frontier_metrics import measure_workbench_release
from glio_noncode.workbench_release_frontier_public_data import default_workbench_release_frontier_fixture
from glio_noncode.workbench_release_frontier_quality_gate import run_workbench_release_quality_gate
from glio_noncode.workbench_release_frontier_review_queue import build_workbench_release_review_queue
from glio_noncode.workbench_release_frontier_schema import default_workbench_release_frontier_schema
from glio_noncode.workbench_release_frontier_reconciliation import reconcile_workbench_release
from glio_noncode.workbench_release_frontier_adapters import build_workbench_release_adapters


class WorkbenchReleaseExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_workbench_release_frontier_fixture()
        cls.evaluation = evaluate_workbench_release_fixture(cls.fixture)

    def test_quality_depth_and_matrices(self) -> None:
        audit = __import__("glio_noncode.workbench_release_frontier_public_data", fromlist=["audit_workbench_release_frontier_data"]).audit_workbench_release_frontier_data(self.fixture)
        quality = run_workbench_release_quality_gate(audit, self.evaluation, build_workbench_release_adapters(), default_workbench_release_frontier_schema(), reconcile_workbench_release(self.fixture, self.evaluation))
        self.assertTrue(quality.accepted)
        self.assertTrue(audit_workbench_release_depth(self.fixture, self.evaluation).accepted)
        self.assertTrue(build_workbench_release_evidence_matrix(self.fixture, self.evaluation).accepted)
        self.assertTrue(evaluate_workbench_release_integrity(self.fixture, self.evaluation).accepted)

    def test_review_queue_and_control_coverage(self) -> None:
        queue = build_workbench_release_review_queue(self.evaluation)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.rows), 12)
        coverage = build_workbench_release_control_coverage(self.evaluation)
        self.assertTrue(coverage.accepted)
        self.assertEqual(len(coverage.rows), 4)

    def test_metrics_and_access_boundary(self) -> None:
        metrics = measure_workbench_release(self.evaluation)
        self.assertEqual(metrics.row_count, 16)
        self.assertEqual(metrics.operation_counts["review_form"], 4)
        access = build_workbench_release_access_manifest(self.fixture)
        self.assertEqual(len(access.sources), 5)
        self.assertIn("individual-level records", access.prohibited_inputs)

    def test_failure_injection_is_conservative(self) -> None:
        report = run_workbench_release_failure_injections()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.cases), 4)


if __name__ == "__main__":
    unittest.main()
