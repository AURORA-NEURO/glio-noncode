"""Executable contract example checks."""

from __future__ import annotations

import unittest

from glio_noncode.cohort_beta_frontier_contract_examples import contract_example_context, contract_example_map, default_cohort_beta_frontier_contract_examples


class CohortBetaFrontierExampleTests(unittest.TestCase):
    def test_examples_cover_all_operation_control_edges(self) -> None:
        examples = default_cohort_beta_frontier_contract_examples()
        self.assertEqual(len(examples), 12)
        self.assertEqual({item.operation for item in examples}, {"C05", "C06", "C07", "C08"})
        self.assertEqual(len(contract_example_map()), 12)
        self.assertTrue(contract_example_context().startswith("GRCh38|glioma|adult|"))

    def test_every_example_declares_a_boundary_and_ceiling(self) -> None:
        for example in default_cohort_beta_frontier_contract_examples():
            self.assertTrue(example.required_boundary)
            self.assertTrue(example.prohibited_inference)
            self.assertTrue(example.content_address)


if __name__ == "__main__":
    unittest.main()
