"""Operational and wording boundary tests for the C05-C08 tranche."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_beta_frontier_claim_dictionary import scan_cohort_beta_frontier_claims
from glio_noncode.cohort_beta_frontier_fixture_manifest import build_cohort_beta_frontier_fixture_manifest
from glio_noncode.cohort_beta_frontier_operational_matrix import default_cohort_beta_frontier_operational_matrix, operational_matrix_summary
from glio_noncode.cohort_beta_frontier_public_data import default_cohort_beta_frontier_fixture
from glio_noncode.cohort_beta_frontier_policy import CohortBetaFrontierDisposition


class CohortBetaFrontierOperationsTests(unittest.TestCase):
    def test_operational_matrix_has_all_dispositions_and_operations(self) -> None:
        report = default_cohort_beta_frontier_operational_matrix()
        summary = operational_matrix_summary(report)
        self.assertTrue(report.accepted)
        self.assertEqual(summary["rule_count"], 15)
        self.assertEqual(summary["by_disposition"][CohortBetaFrontierDisposition.PUBLISH.value], 5)
        self.assertEqual(summary["by_disposition"][CohortBetaFrontierDisposition.REVIEW.value], 5)
        self.assertEqual(summary["by_disposition"][CohortBetaFrontierDisposition.QUARANTINE.value], 5)
        self.assertGreaterEqual(summary["by_operation"]["C05"], 3)

    def test_manifest_and_claim_scan_preserve_release_ceiling(self) -> None:
        manifest = build_cohort_beta_frontier_fixture_manifest(default_cohort_beta_frontier_fixture())
        scan = scan_cohort_beta_frontier_claims("This recurrence summary does not establish a driver, significant result, clinical outcome, or treatment effect.")
        self.assertTrue(manifest.accepted)
        self.assertEqual(len(manifest.for_operation("C08")), 4)
        self.assertIn("driver", scan["prohibited"])
        self.assertIn("clinical", scan["prohibited"])
        self.assertIn("treatment", scan["prohibited"])


if __name__ == "__main__":
    unittest.main()
