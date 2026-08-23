from __future__ import annotations

import unittest

from glio_noncode.deployment_frontier_contracts import DeploymentFrontierOperation, DeploymentFrontierRole
from glio_noncode.deployment_frontier_fixture_eval import audit_deployment_frontier_context, evaluate_deployment_frontier_fixture
from glio_noncode.deployment_frontier_operations import run_deployment_frontier_operation
from glio_noncode.deployment_frontier_public_data import audit_deployment_frontier_data, default_deployment_frontier_fixture


class DeploymentFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_deployment_frontier_fixture()
        cls.audit = audit_deployment_frontier_data(cls.fixture)
        cls.evaluation = evaluate_deployment_frontier_fixture(cls.fixture)

    def test_public_aggregate_fixture_shape(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(audit_deployment_frontier_context(self.fixture), ())
        self.assertTrue(all(source.uri.startswith("https://") for source in self.fixture.sources))

    def test_all_rows_evaluate_with_five_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 80)
        self.assertEqual(self.evaluation.failed_checks, 0)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.evaluation.checks))

    def test_positive_operation_states(self) -> None:
        expected = {
            DeploymentFrontierOperation.PRIVACY_SECURITY_POLICY: "ready",
            DeploymentFrontierOperation.LOCAL_DEPLOYMENT_BUNDLE: "ready",
            DeploymentFrontierOperation.FEDERATED_EXECUTION: "ready",
            DeploymentFrontierOperation.RELEASE_ROLLBACK: "released",
        }
        for record in self.fixture.positive_records:
            result = run_deployment_frontier_operation(record.operation, record.payload)
            self.assertEqual(result.state.value, expected[record.operation])
            self.assertEqual(result.issue_codes, ())

    def test_controls_remain_negative(self) -> None:
        for record in self.fixture.control_records:
            result = run_deployment_frontier_operation(record.operation, record.payload)
            self.assertEqual(record.role, DeploymentFrontierRole.CONTROL)
            self.assertEqual(result.state, record.expected_state)
            self.assertTrue(set(record.expected_issue_codes) <= set(result.issue_codes))
            self.assertTrue(result.issue_codes)

    def test_safe_outputs_do_not_repeat_secret_markers(self) -> None:
        serialized = str(self.evaluation.to_dict()).lower()
        self.assertNotIn("signing_secret", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("password", serialized)


if __name__ == "__main__":
    unittest.main()
