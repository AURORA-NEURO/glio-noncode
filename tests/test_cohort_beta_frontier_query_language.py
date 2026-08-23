"""Review query language tests."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_beta_frontier_query_language import execute_cohort_beta_frontier_query, parse_cohort_beta_frontier_query, query_examples
from glio_noncode.cohort_beta_frontier_runtime import run_cohort_beta_frontier_runtime
from glio_noncode.cohort_beta_frontier_views import build_cohort_beta_frontier_review_view


class CohortBetaFrontierQueryLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_cohort_beta_frontier_runtime()
        cls.view = build_cohort_beta_frontier_review_view(cls.runtime.evaluation, cls.runtime.policy, cls.runtime.fixture.context_key)

    def test_query_examples_are_deterministic(self) -> None:
        supported = execute_cohort_beta_frontier_query(self.view, parse_cohort_beta_frontier_query(query_examples()["supported"]))
        foreign = execute_cohort_beta_frontier_query(self.view, parse_cohort_beta_frontier_query(query_examples()["foreign"]))
        operation = execute_cohort_beta_frontier_query(self.view, parse_cohort_beta_frontier_query(query_examples()["operation"]))
        self.assertEqual(supported.total_matches, 4)
        self.assertEqual(foreign.total_matches, 4)
        self.assertEqual(operation.total_matches, 4)
        self.assertTrue(all(row.operation == "C08" for row in operation.rows))

    def test_query_negation_and_limit(self) -> None:
        plan = parse_cohort_beta_frontier_query("disposition=quarantine and !state=out_of_domain", limit=2)
        result = execute_cohort_beta_frontier_query(self.view, plan)
        self.assertEqual(result.total_matches, 4)
        self.assertEqual(len(result.rows), 2)

    def test_invalid_query_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_cohort_beta_frontier_query("not-a-clause")


if __name__ == "__main__":
    unittest.main()
