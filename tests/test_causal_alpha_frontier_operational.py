from __future__ import annotations

import unittest

from glio_noncode.causal_alpha_frontier_operational import build_causal_alpha_frontier_operational_matrix
from glio_noncode.causal_alpha_frontier_policy import CausalAlphaFrontierDisposition
from glio_noncode.causal_alpha_frontier_public_data import default_causal_alpha_frontier_fixture
from glio_noncode.causal_alpha_frontier_runtime import run_causal_alpha_frontier_runtime


class CausalAlphaFrontierOperationalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = run_causal_alpha_frontier_runtime(default_causal_alpha_frontier_fixture(), run_id="alpha-operational-tests")

    def test_matrix_is_accepted_and_counts_close(self) -> None:
        matrix = self.runtime.operational
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.cells), 16)
        self.assertEqual(matrix.allowed_count + matrix.review_count + matrix.quarantine_count, 16)
        self.assertEqual(matrix.allowed_count, 3)
        self.assertEqual(matrix.review_count, 9)
        self.assertEqual(matrix.quarantine_count, 4)

    def test_allowed_cells_are_exact_context_supported_rows(self) -> None:
        allowed = [item for item in self.runtime.operational.cells if item.disposition is CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE]
        self.assertEqual({item.record_id for item in allowed}, {"D11-C09-P", "D11-C10-P", "D11-C11-P"})
        self.assertTrue(all(not item.blocking for item in allowed))
        self.assertTrue(all(item.action == "allow descriptive export" for item in allowed))

    def test_foreign_context_cells_are_quarantined(self) -> None:
        quarantine = [item for item in self.runtime.operational.cells if item.disposition is CausalAlphaFrontierDisposition.QUARANTINE]
        self.assertEqual({item.record_id for item in quarantine}, {"D11-C09-C3", "D11-C10-C3", "D11-C11-C3", "D11-C12-C3"})
        self.assertTrue(all(item.blocking for item in quarantine))
        self.assertTrue(all(item.action == "quarantine and reconcile context" for item in quarantine))
        self.assertTrue(all(item.owner_scope == "exact-context review" for item in quarantine))

    def test_review_cells_preserve_negative_and_contradictory_states(self) -> None:
        review = [item for item in self.runtime.operational.cells if item.disposition is CausalAlphaFrontierDisposition.REVIEW]
        self.assertEqual(len(review), 9)
        by_id = {item.record_id: item for item in review}
        self.assertEqual(by_id["D11-C11-C2"].reason, "conflicting or negative evidence requires explicit review")
        self.assertEqual(by_id["D11-C12-C1"].reason, "conflicting or negative evidence requires explicit review")
        self.assertFalse(by_id["D11-C11-C2"].blocking)

    def test_each_cell_has_a_stable_address_and_reason(self) -> None:
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.runtime.operational.cells))
        self.assertEqual(len({item.content_address for item in self.runtime.operational.cells}), 16)
        self.assertTrue(all(item.reason for item in self.runtime.operational.cells))
        self.assertTrue(all(item.owner_scope for item in self.runtime.operational.cells))

    def test_policy_excluded_claims_are_consistent(self) -> None:
        excluded = {claim for decision in self.runtime.decisions for claim in decision.excluded_claims}
        self.assertEqual(excluded, {"causal identification", "clinical diagnosis", "treatment recommendation", "prognosis"})
        self.assertTrue(all(len(item.allowed_claims) >= 1 for item in self.runtime.decisions))

    def test_review_queue_has_required_evidence_for_every_non_allowed_row(self) -> None:
        review_ids = {item.record_id for item in self.runtime.review.items}
        non_allowed = {item.record_id for item in self.runtime.decisions if item.disposition is not CausalAlphaFrontierDisposition.ALLOW_DESCRIPTIVE}
        self.assertEqual(review_ids, non_allowed)
        self.assertTrue(all(item.required_evidence for item in self.runtime.review.items))
        self.assertEqual(len({item.review_id for item in self.runtime.review.items}), 13)

    def test_review_queue_blocking_items_are_foreign_only(self) -> None:
        self.assertEqual({item.record_id for item in self.runtime.review.blocking_items}, {"D11-C09-C3", "D11-C10-C3", "D11-C11-C3", "D11-C12-C3"})

    def test_claim_boundary_matches_operational_matrix(self) -> None:
        boundary = self.runtime.boundary
        self.assertTrue(boundary.accepted)
        self.assertEqual(boundary.violation_codes, ())
        self.assertEqual(len(boundary.allowed_claims), 5)
        self.assertEqual(len(boundary.excluded_claims), 5)
        self.assertEqual(boundary.boundary, "public_aggregate_non_patient")

    def test_rebuild_of_matrix_has_same_content_address(self) -> None:
        fixture = default_causal_alpha_frontier_fixture()
        rebuilt = build_causal_alpha_frontier_operational_matrix(fixture, self.runtime.decisions, self.runtime.review)
        self.assertEqual(rebuilt.content_address, self.runtime.operational.content_address)
        self.assertEqual(rebuilt.to_dict(False), self.runtime.operational.to_dict(False))

    def test_runtime_assurance_requires_operational_acceptance(self) -> None:
        self.assertTrue(self.runtime.assurance.accepted)
        operational_check = next(item for item in self.runtime.assurance.checks if item["check_id"] == "operational")
        self.assertTrue(operational_check["passed"])


if __name__ == "__main__":
    unittest.main()
