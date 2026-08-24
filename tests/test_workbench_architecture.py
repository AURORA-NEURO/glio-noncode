"""D15 workbench architecture contract and runtime tests."""

from __future__ import annotations

import unittest

from glio_noncode.workbench_architecture_audit import deep_audit_workbench_architecture
from glio_noncode.workbench_architecture_compliance import assess_workbench_architecture_compliance
from glio_noncode.workbench_architecture_contract_matrix import (
    workbench_architecture_contract_matrix,
)
from glio_noncode.workbench_architecture_data_dictionary import (
    workbench_architecture_data_dictionary,
)
from glio_noncode.workbench_architecture_depth import assess_workbench_architecture_depth
from glio_noncode.workbench_architecture_ledger import workbench_architecture_ledger_is_closed
from glio_noncode.workbench_architecture_lineage import (
    workbench_architecture_lineage_gaps,
    workbench_architecture_lineage_rows,
)
from glio_noncode.workbench_architecture_metrics import (
    workbench_architecture_metric_invariants,
    workbench_architecture_metrics,
)
from glio_noncode.workbench_architecture_operations import evaluate_workbench_architecture_fixture
from glio_noncode.workbench_architecture_plan import build_workbench_architecture_plan
from glio_noncode.workbench_architecture_public_data import (
    audit_workbench_architecture_data,
    default_workbench_architecture_fixture,
)
from glio_noncode.workbench_architecture_query import query_workbench_architecture
from glio_noncode.workbench_architecture_replay import replay_workbench_architecture_fixture
from glio_noncode.workbench_architecture_review import build_workbench_architecture_review_queue
from glio_noncode.workbench_architecture_runtime import (
    WORKBENCH_ARCHITECTURE_STAGE_IDS,
    run_workbench_architecture,
)
from glio_noncode.workbench_architecture_schema import (
    validate_workbench_architecture_fixture,
    validate_workbench_architecture_mapping,
)


class WorkbenchArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_workbench_architecture_fixture()
        cls.audit = audit_workbench_architecture_data(cls.fixture)
        cls.evaluation = evaluate_workbench_architecture_fixture(cls.fixture)
        cls.runtime = run_workbench_architecture(cls.fixture)

    def test_fixture_and_audit_shape(self) -> None:
        self.assertEqual(len(self.fixture.sources), 20)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertTrue(self.audit.accepted)
        self.assertEqual(validate_workbench_architecture_mapping(self.fixture.to_dict()), ())
        self.assertTrue(validate_workbench_architecture_fixture(self.fixture))

    def test_delegate_states_and_controls_are_retained(self) -> None:
        observed = {item.case_id: item for item in self.evaluation.executions}
        expected = {
            "D15-C01-POSITIVE-001": ("partial", ("missing_dossier",)),
            "D15-C01-CONTROL-A-001": ("out_of_domain", ("context_mismatch",)),
            "D15-C04-CONTROL-C-001": ("invalid", ("invalid_track_input",)),
            "D15-C06-CONTROL-B-001": ("incomplete", ("missing_mediator",)),
            "D15-C07-CONTROL-A-001": ("partial", ("foreign_component", "unreconciled_components")),
            "D15-C11-POSITIVE-001": ("verified", ()),
            "D15-C13-POSITIVE-001": ("reviewed", ()),
            "D15-C16-CONTROL-C-001": ("review", ("criterion_failed",)),
        }
        for case_id, (state, issues) in expected.items():
            self.assertEqual(observed[case_id].observed_state.value, state)
            self.assertEqual(observed[case_id].observed_issue_codes, issues)

    def test_evaluation_receipts_and_check_depth(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 64)
        self.assertEqual(len(self.evaluation.receipts), 64)
        self.assertEqual(len(self.evaluation.checks), 458)
        self.assertTrue(all(item.passed for item in self.evaluation.checks))

    def test_plan_review_lineage_ledger_and_replay(self) -> None:
        plan = build_workbench_architecture_plan(self.fixture)
        review = build_workbench_architecture_review_queue(self.evaluation, self.fixture)
        rows = workbench_architecture_lineage_rows(self.fixture)
        replay = replay_workbench_architecture_fixture(self.fixture)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.nodes), 16)
        self.assertGreaterEqual(len(review.items), 48)
        self.assertGreaterEqual(len(rows), 64)
        self.assertEqual(workbench_architecture_lineage_gaps(self.fixture), ())
        self.assertTrue(workbench_architecture_ledger_is_closed(self.runtime.ledger))
        self.assertEqual(len(self.runtime.ledger.events), 80)
        self.assertTrue(replay.accepted)

    def test_metrics_depth_quality_release_and_stages(self) -> None:
        metrics = workbench_architecture_metrics(self.fixture, self.evaluation)
        depth = assess_workbench_architecture_depth(self.fixture, self.evaluation)
        self.assertEqual(workbench_architecture_metric_invariants(metrics), ())
        self.assertEqual(metrics["check_count"], 458)
        self.assertEqual(depth.case_count, 64)
        self.assertTrue(self.runtime.accepted)
        self.assertTrue(self.runtime.quality.accepted)
        self.assertEqual(self.runtime.release.state.value, "published")
        self.assertEqual(len(self.runtime.artifacts), 6)
        self.assertEqual(
            tuple(item.stage_id for item in self.runtime.stages), WORKBENCH_ARCHITECTURE_STAGE_IDS
        )

    def test_public_boundary_and_reporting_inputs(self) -> None:
        compliance = assess_workbench_architecture_compliance(self.fixture)
        matrix = workbench_architecture_contract_matrix(self.fixture)
        dictionary = workbench_architecture_data_dictionary(self.fixture)
        audit = deep_audit_workbench_architecture(self.fixture)
        rows = query_workbench_architecture(
            fixture=self.fixture, evaluation=self.evaluation, operation="D15-C14"
        )
        self.assertTrue(compliance.accepted)
        self.assertEqual(compliance.forbidden_keys, ())
        self.assertEqual(len(matrix), 16)
        self.assertGreaterEqual(len(dictionary), 13)
        self.assertTrue(audit["accepted"])
        self.assertEqual(len(rows), 4)


if __name__ == "__main__":
    unittest.main()
