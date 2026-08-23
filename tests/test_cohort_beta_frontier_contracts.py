"""Contract tests for claim, error, manifest, and mutation boundaries."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_beta_frontier_claim_dictionary import CohortBetaFrontierClaimClass, default_cohort_beta_frontier_claim_dictionary, scan_cohort_beta_frontier_claims
from glio_noncode.cohort_beta_frontier_error_taxonomy import CohortBetaFrontierErrorClass, default_cohort_beta_frontier_error_taxonomy
from glio_noncode.cohort_beta_frontier_fixture_manifest import build_cohort_beta_frontier_fixture_manifest, manifest_summary
from glio_noncode.cohort_beta_frontier_fixture_mutations import default_cohort_beta_frontier_mutation_cases, evaluate_cohort_beta_frontier_mutations
from glio_noncode.cohort_beta_frontier_public_data import default_cohort_beta_frontier_fixture
from glio_noncode.cohort_beta_frontier_release_checks import run_cohort_beta_frontier_release_checks
from glio_noncode.cohort_beta_frontier_runtime import run_cohort_beta_frontier_runtime


class CohortBetaFrontierContractDepthTests(unittest.TestCase):
    def test_claim_dictionary_separates_allowed_review_and_prohibited_terms(self) -> None:
        dictionary = default_cohort_beta_frontier_claim_dictionary()
        result = scan_cohort_beta_frontier_claims("recurrent burden driver significant clinical treatment")
        self.assertTrue(dictionary.accepted)
        self.assertIn("burden", result["allowed"])
        self.assertIn("driver", result["prohibited"])
        self.assertIn("significant", result["prohibited"])
        self.assertEqual(dictionary.lookup("treatment").claim_class, CohortBetaFrontierClaimClass.PROHIBITED)

    def test_error_taxonomy_covers_all_release_classes(self) -> None:
        taxonomy = default_cohort_beta_frontier_error_taxonomy()
        self.assertTrue(taxonomy.accepted)
        self.assertEqual(len(taxonomy.codes), 8)
        self.assertEqual(len(taxonomy.by_class(CohortBetaFrontierErrorClass.COMPARATOR)), 2)
        self.assertTrue(taxonomy.by_code("GNC-C05-RELEASE-001").blocking)

    def test_fixture_manifest_preserves_foreign_context_and_counts(self) -> None:
        manifest = build_cohort_beta_frontier_fixture_manifest(default_cohort_beta_frontier_fixture())
        summary = manifest_summary(manifest)
        self.assertTrue(manifest.accepted)
        self.assertEqual(manifest.positive_count, 4)
        self.assertEqual(manifest.control_count, 12)
        self.assertEqual(summary["operations"], {"C05": 4, "C06": 4, "C07": 4, "C08": 4})
        self.assertTrue(all(row.context_key for row in manifest.rows))

    def test_release_checks_and_mutation_cases_are_closed(self) -> None:
        fixture = default_cohort_beta_frontier_fixture()
        runtime = run_cohort_beta_frontier_runtime(fixture)
        checks = run_cohort_beta_frontier_release_checks(fixture, runtime.evaluation, runtime.quality and __import__("glio_noncode.cohort_beta_frontier_safety", fromlist=["evaluate_cohort_beta_frontier_safety"]).evaluate_cohort_beta_frontier_safety(runtime.evaluation, runtime.policy, runtime.claim_boundary), runtime.claim_boundary, runtime.replay)
        mutations = evaluate_cohort_beta_frontier_mutations(fixture, default_cohort_beta_frontier_mutation_cases())
        self.assertTrue(checks.accepted)
        self.assertEqual(checks.blocking_failure_count, 0)
        self.assertTrue(mutations.accepted)
        self.assertEqual(len(mutations.cases), 10)


if __name__ == "__main__":
    unittest.main()
