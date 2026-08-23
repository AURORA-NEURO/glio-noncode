"""Additional depth tests for public aggregate controls and projections."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_beta import CohortBetaState
from glio_noncode.cohort_beta_frontier_access_model import CohortBetaFrontierAccessState, default_cohort_beta_frontier_access_requests, evaluate_cohort_beta_frontier_access
from glio_noncode.cohort_beta_frontier_benchmark import build_cohort_beta_frontier_benchmark_report
from glio_noncode.cohort_beta_frontier_calibration import build_cohort_beta_frontier_calibration_report
from glio_noncode.cohort_beta_frontier_comparator import build_cohort_beta_frontier_comparator_report
from glio_noncode.cohort_beta_frontier_evidence_matrix import build_cohort_beta_frontier_evidence_matrix
from glio_noncode.cohort_beta_frontier_fixture_eval import evaluate_cohort_beta_frontier_fixture
from glio_noncode.cohort_beta_frontier_fixture_mutations import evaluate_cohort_beta_frontier_mutations
from glio_noncode.cohort_beta_frontier_module_catalog import default_cohort_beta_frontier_module_catalog
from glio_noncode.cohort_beta_frontier_operation_notes import operation_note_map
from glio_noncode.cohort_beta_frontier_public_data import default_cohort_beta_frontier_fixture
from glio_noncode.cohort_beta_frontier_publication import build_cohort_beta_frontier_publication_plan
from glio_noncode.cohort_beta_frontier_review import build_cohort_beta_frontier_review_queue
from glio_noncode.cohort_beta_frontier_review_protocol import build_cohort_beta_frontier_review_protocol
from glio_noncode.cohort_beta_frontier_runtime import run_cohort_beta_frontier_runtime
from glio_noncode.cohort_beta_frontier_safety import evaluate_cohort_beta_frontier_safety


class CohortBetaFrontierDepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_cohort_beta_frontier_fixture()
        cls.evaluation = evaluate_cohort_beta_frontier_fixture(cls.fixture)
        cls.runtime = run_cohort_beta_frontier_runtime(cls.fixture)

    def test_module_catalog_covers_many_layers(self) -> None:
        catalog = default_cohort_beta_frontier_module_catalog()
        self.assertTrue(catalog.accepted)
        self.assertGreaterEqual(len(catalog.entries), 32)
        self.assertGreaterEqual(catalog.layer_count, 10)
        self.assertEqual(len(catalog.for_operation("C05")), 10)
        self.assertEqual(len(operation_note_map()), 4)

    def test_comparator_and_calibration_surfaces_are_explicit(self) -> None:
        comparator = build_cohort_beta_frontier_comparator_report(self.fixture, self.evaluation)
        calibration = build_cohort_beta_frontier_calibration_report(self.fixture, comparator)
        self.assertTrue(comparator.accepted)
        self.assertEqual(len(comparator.receipts), 4)
        self.assertEqual(calibration.state.value, "descriptive")
        self.assertFalse(calibration.accepted)
        self.assertEqual(sum(item.blocking and not item.present for item in calibration.requirements), 4)

    def test_safety_publication_and_access_are_separate_planes(self) -> None:
        boundary = self.runtime.claim_boundary
        safety = evaluate_cohort_beta_frontier_safety(self.evaluation, self.runtime.policy, boundary)
        plan = build_cohort_beta_frontier_publication_plan(self.fixture, self.evaluation, self.runtime.policy, boundary)
        access = evaluate_cohort_beta_frontier_access(default_cohort_beta_frontier_access_requests())
        self.assertTrue(safety.accepted)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.publishable_records), 4)
        self.assertEqual(access.deny_count, 1)
        self.assertEqual(access.mask_count, 1)
        self.assertEqual(access.decisions[-1].decision, CohortBetaFrontierAccessState.DENY)

    def test_review_protocol_keeps_all_open_paths_unresolved(self) -> None:
        queue = build_cohort_beta_frontier_review_queue(self.evaluation, self.runtime.policy)
        protocol = build_cohort_beta_frontier_review_protocol(queue)
        self.assertTrue(protocol.accepted)
        self.assertEqual(len(protocol.decisions), 12)
        self.assertTrue(all(item.unresolved_questions for item in protocol.decisions))

    def test_mutations_and_evidence_matrix_block_drift(self) -> None:
        mutations = evaluate_cohort_beta_frontier_mutations(self.fixture)
        matrix = build_cohort_beta_frontier_evidence_matrix(self.fixture, self.evaluation)
        benchmark = build_cohort_beta_frontier_benchmark_report(self.fixture, self.evaluation)
        self.assertTrue(mutations.accepted)
        self.assertEqual(len(mutations.results), 10)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.cells), 16)
        self.assertTrue(benchmark.accepted)
        self.assertLessEqual(benchmark.total_work_units, benchmark.max_work_units)


if __name__ == "__main__":
    unittest.main()
