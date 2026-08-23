from __future__ import annotations

import unittest

from glio_noncode.validation_design_frontier_adapters import build_validation_design_adapters, execute_validation_design_adapter
from glio_noncode.validation_design_frontier_contracts import ValidationDesignOperation, ValidationDesignState
from glio_noncode.validation_design_frontier_depth import audit_validation_design_depth
from glio_noncode.validation_design_frontier_fixture_eval import evaluate_validation_design_fixture
from glio_noncode.validation_design_frontier_public_data import default_validation_design_frontier_fixture, validation_design_frontier_fixture_json
from glio_noncode.validation_design_frontier_thresholds import build_validation_design_threshold_report


class ValidationDesignExtensionTests(unittest.TestCase):
    def test_adapter_schema_rejects_empty_payload(self) -> None:
        result = execute_validation_design_adapter(build_validation_design_adapters(), ValidationDesignOperation.GAP_ANALYSIS, {})
        self.assertEqual(result.state, ValidationDesignState.REJECTED)
        self.assertIn("schema_invalid", result.issue_codes)

    def test_depth_and_thresholds_are_closed(self) -> None:
        fixture = default_validation_design_frontier_fixture()
        evaluation = evaluate_validation_design_fixture(fixture)
        self.assertTrue(audit_validation_design_depth(fixture, evaluation).accepted)
        threshold = build_validation_design_threshold_report()
        self.assertTrue(threshold.accepted)
        self.assertEqual(threshold.thresholds["total_checks"], 80)

    def test_fixture_json_is_stable(self) -> None:
        fixture = default_validation_design_frontier_fixture()
        text = validation_design_frontier_fixture_json(fixture)
        self.assertIn(fixture.fixture_id, text)
        self.assertIn(fixture.content_address, text)
        self.assertTrue(text.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
