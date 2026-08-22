from __future__ import annotations

import unittest

from glio_noncode.link_frontier_contracts import default_link_frontier_contracts
from glio_noncode.link_frontier_depth import run_link_frontier_depth_audit
from glio_noncode.link_frontier_fixture_eval import evaluate_link_frontier_fixture
from glio_noncode.link_frontier_public_data import (
    LinkFrontierOperation,
    default_link_frontier_fixture,
)


class LinkFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_link_frontier_fixture()
        self.evaluation = evaluate_link_frontier_fixture(self.fixture)
        self.audit = run_link_frontier_depth_audit(
            self.fixture,
            evaluation=self.evaluation,
            contracts=default_link_frontier_contracts(),
        )

    def test_depth_audit_is_accepted_with_fifty_one_checks(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.audit.checks), 51)
        self.assertEqual(self.audit.passed_count, 51)
        self.assertEqual(self.audit.failed_check_ids, ())
        self.assertTrue(self.audit.content_address)

    def test_depth_audit_has_one_operation_report_per_capability_band(self) -> None:
        self.assertEqual(len(self.audit.operations), 4)
        self.assertEqual(
            {item.operation for item in self.audit.operations},
            set(LinkFrontierOperation),
        )
        self.assertEqual(
            {item.check_count for item in self.audit.operations},
            {12, 13},
        )
        self.assertTrue(all(item.accepted for item in self.audit.operations))
        self.assertTrue(all(item.content_address for item in self.audit.operations))

    def test_dependence_depth_retains_raw_and_corrected_support(self) -> None:
        checks = {item.check_id: item for item in self.audit.checks}
        for check_id in (
            "C13:links_present",
            "C13:raw_support_retained",
            "C13:corrected_support_bounded",
            "C13:group_size_retained",
            "C13:context_retained",
            "C13:zero_control",
            "C13:address",
        ):
            self.assertTrue(checks[check_id].passed, check_id)
        self.assertEqual(
            self.audit.operations[0].issue_codes,
            ("empty_dependence_input", "invalid_dependence_input", "zero_corrected_support"),
        )

    def test_ranking_depth_retains_identity_alternatives_and_top_mapping(self) -> None:
        checks = {item.check_id: item for item in self.audit.checks}
        for check_id in (
            "C14:ranks_present",
            "C14:rank_sequence",
            "C14:gene_identity",
            "C14:component_scores",
            "C14:alternative_gene",
            "C14:top_mapping",
            "C14:zero_control",
            "C14:address",
        ):
            self.assertTrue(checks[check_id].passed, check_id)
        self.assertIn("zero_rank_support", self.audit.operations[1].issue_codes)

    def test_calibration_depth_retains_thresholds_and_abstention_controls(self) -> None:
        checks = {item.check_id: item for item in self.audit.checks}
        for check_id in (
            "C15:decision_present",
            "C15:accepted_id",
            "C15:uncertainty_retained",
            "C15:error_retained",
            "C15:thresholds_declared",
            "C15:uncertainty_control",
            "C15:error_control",
            "C15:address",
        ):
            self.assertTrue(checks[check_id].passed, check_id)
        self.assertIn("link_uncertainty_high", self.audit.operations[2].issue_codes)
        self.assertIn("link_calibration_error_high", self.audit.operations[2].issue_codes)

    def test_publication_depth_retains_bundle_receipt_and_context_controls(self) -> None:
        checks = {item.check_id: item for item in self.audit.checks}
        for check_id in (
            "C16:published_state",
            "C16:bundle_address",
            "C16:records_address",
            "C16:link_ids",
            "C16:context",
            "C16:context_control",
            "C16:source_control",
            "C16:address",
        ):
            self.assertTrue(checks[check_id].passed, check_id)
        self.assertIn("publication_context_mismatch", self.audit.operations[3].issue_codes)
        self.assertIn("invalid_publication_input", self.audit.operations[3].issue_codes)

    def test_contract_depth_checks_are_operation_scoped(self) -> None:
        contract_checks = [item for item in self.audit.checks if item.check_id.startswith("contract:")]
        self.assertEqual(len(contract_checks), 20)
        self.assertEqual({item.operation for item in contract_checks}, set(LinkFrontierOperation))
        self.assertTrue(all(item.passed for item in contract_checks))
        self.assertTrue(all(item.expected is True for item in contract_checks if item.check_id.endswith((":fields", ":positive", ":controls", ":issues", ":limits"))))

    def test_depth_serialization_exposes_summary_fields(self) -> None:
        payload = self.audit.to_dict()
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_count"], 51)
        self.assertEqual(payload["failed_check_ids"], [])
        self.assertEqual(len(payload["operations"]), 4)
        self.assertTrue(all("content_address" in row for row in payload["checks"]))


if __name__ == "__main__":
    unittest.main()
