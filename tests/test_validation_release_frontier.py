from __future__ import annotations

import unittest

from glio_noncode.validation_release_frontier_contracts import ValidationReleaseOperation, ValidationReleaseRole
from glio_noncode.validation_release_frontier_fixture_eval import audit_validation_release_context, evaluate_validation_release_fixture
from glio_noncode.validation_release_frontier_operations import run_validation_release_operation
from glio_noncode.validation_release_frontier_public_data import audit_validation_release_frontier_data, default_validation_release_frontier_fixture


class ValidationReleaseFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_validation_release_frontier_fixture()
        cls.audit = audit_validation_release_frontier_data(cls.fixture)
        cls.evaluation = evaluate_validation_release_fixture(cls.fixture)

    def test_public_aggregate_shape(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(audit_validation_release_context(self.fixture), ())

    def test_every_row_has_five_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 80)
        self.assertEqual(self.evaluation.failed_checks, 0)

    def test_positive_operation_states(self) -> None:
        expected = {ValidationReleaseOperation.OFF_TARGET_RISK: "ready", ValidationReleaseOperation.VALUE_OF_INFORMATION: "ready", ValidationReleaseOperation.EXPERIMENT_PACKAGE: "packaged", ValidationReleaseOperation.CLAIM_UPDATE: "updated"}
        for record in self.fixture.positive_records:
            result = run_validation_release_operation(record.operation, record.payload)
            self.assertEqual(result.state.value, expected[record.operation])
            self.assertEqual(result.issue_codes, ())

    def test_controls_keep_failure_boundaries(self) -> None:
        for record in self.fixture.control_records:
            result = run_validation_release_operation(record.operation, record.payload)
            self.assertEqual(record.role, ValidationReleaseRole.CONTROL)
            self.assertEqual(result.state, record.expected_state)
            self.assertTrue(set(record.expected_issue_codes) <= set(result.issue_codes))

    def test_outputs_are_safe_projections(self) -> None:
        serialized = str(self.evaluation.to_dict()).lower()
        for marker in ("password", "api_key", "signing_secret", "access_token"):
            self.assertNotIn(marker, serialized)


if __name__ == "__main__":
    unittest.main()
