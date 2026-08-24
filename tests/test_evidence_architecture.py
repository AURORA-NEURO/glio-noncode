"""D14 evidence architecture contract and runtime tests."""

from __future__ import annotations

import unittest

from glio_noncode.evidence_architecture_audit import deep_audit_evidence_architecture
from glio_noncode.evidence_architecture_compliance import assess_evidence_architecture_compliance
from glio_noncode.evidence_architecture_contract_matrix import evidence_architecture_contract_matrix
from glio_noncode.evidence_architecture_data_dictionary import evidence_architecture_data_dictionary
from glio_noncode.evidence_architecture_depth import assess_evidence_architecture_depth
from glio_noncode.evidence_architecture_ledger import evidence_architecture_ledger_is_closed
from glio_noncode.evidence_architecture_lineage import (
    evidence_architecture_lineage_gaps,
    evidence_architecture_lineage_rows,
)
from glio_noncode.evidence_architecture_metrics import (
    evidence_architecture_metric_invariants,
    evidence_architecture_metrics,
)
from glio_noncode.evidence_architecture_operations import evaluate_evidence_architecture_fixture
from glio_noncode.evidence_architecture_plan import build_evidence_architecture_plan
from glio_noncode.evidence_architecture_public_data import (
    audit_evidence_architecture_data,
    default_evidence_architecture_fixture,
)
from glio_noncode.evidence_architecture_query import query_evidence_architecture
from glio_noncode.evidence_architecture_replay import replay_evidence_architecture_fixture
from glio_noncode.evidence_architecture_review import build_evidence_architecture_review_queue
from glio_noncode.evidence_architecture_runtime import (
    EVIDENCE_ARCHITECTURE_STAGE_IDS,
    run_evidence_architecture,
)
from glio_noncode.evidence_architecture_schema import (
    validate_evidence_architecture_fixture,
    validate_evidence_architecture_mapping,
)


class EvidenceArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_evidence_architecture_fixture()
        cls.audit = audit_evidence_architecture_data(cls.fixture)
        cls.evaluation = evaluate_evidence_architecture_fixture(cls.fixture)
        cls.runtime = run_evidence_architecture(cls.fixture)

    def test_fixture_and_audit_shape(self) -> None:
        self.assertEqual(len(self.fixture.sources), 19)
        self.assertEqual(len(self.fixture.operations), 16)
        self.assertEqual(len(self.fixture.cases), 64)
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)
        self.assertTrue(self.audit.accepted)
        self.assertEqual(validate_evidence_architecture_mapping(self.fixture.to_dict()), ())
        self.assertTrue(validate_evidence_architecture_fixture(self.fixture))

    def test_delegate_states_and_controls_are_retained(self) -> None:
        observed = {item.case_id: item for item in self.evaluation.executions}
        expected = {
            "D14-C01-POS-001": ("partial", ("missing_required_field",)),
            "D14-C04-POS-001": ("contradictory", ("contradiction_unresolved",)),
            "D14-C02-CTRL-002": ("invalid", ("graph_context_mismatch",)),
            "D14-C08-CTRL-003": ("review_required", ("required_role",)),
            "D14-C09-POS-001": ("adjudicated", ()),
            "D14-C13-POS-001": ("reclassified", ()),
            "D14-C14-CTRL-002": ("blocked", ("supersession_cycle",)),
            "D14-C16-CTRL-001": ("review", ("dossier_expired",)),
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
        self.assertTrue(all(item.output_address for item in self.evaluation.executions))

    def test_plan_review_lineage_ledger_and_replay(self) -> None:
        plan = build_evidence_architecture_plan(self.fixture)
        review = build_evidence_architecture_review_queue(self.evaluation, self.fixture)
        rows = evidence_architecture_lineage_rows(self.fixture)
        ledger = self.runtime.ledger
        replay = replay_evidence_architecture_fixture(self.fixture)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.nodes), 16)
        self.assertGreaterEqual(len(review.items), 48)
        self.assertEqual(len(rows), 92)
        self.assertEqual(evidence_architecture_lineage_gaps(self.fixture), ())
        self.assertTrue(evidence_architecture_ledger_is_closed(ledger))
        self.assertEqual(len(ledger.events), 80)
        self.assertTrue(replay.accepted)

    def test_metrics_depth_quality_release_and_stages(self) -> None:
        metrics = evidence_architecture_metrics(self.fixture, self.evaluation)
        depth = assess_evidence_architecture_depth(self.fixture, self.evaluation)
        self.assertEqual(evidence_architecture_metric_invariants(metrics), ())
        self.assertEqual(metrics["check_count"], 458)
        self.assertEqual(depth.case_count, 64)
        self.assertEqual(depth.issue_code_count, 42)
        self.assertTrue(self.runtime.accepted)
        self.assertTrue(self.runtime.quality.accepted)
        self.assertEqual(self.runtime.release.state.value, "published")
        self.assertEqual(len(self.runtime.artifacts), 6)
        self.assertEqual(len(self.runtime.stages), 24)
        self.assertEqual(
            tuple(item.stage_id for item in self.runtime.stages), EVIDENCE_ARCHITECTURE_STAGE_IDS
        )

    def test_public_boundary_and_reporting_inputs(self) -> None:
        compliance = assess_evidence_architecture_compliance(self.fixture)
        matrix = evidence_architecture_contract_matrix(self.fixture)
        dictionary = evidence_architecture_data_dictionary(self.fixture)
        audit = deep_audit_evidence_architecture(self.fixture)
        rows = query_evidence_architecture(
            fixture=self.fixture, evaluation=self.evaluation, operation="D14-C14"
        )
        self.assertTrue(compliance.accepted)
        self.assertEqual(compliance.forbidden_keys, ())
        self.assertEqual(len(matrix), 16)
        self.assertGreaterEqual(len(dictionary), 13)
        self.assertTrue(audit["accepted"])
        self.assertEqual(len(rows), 4)


if __name__ == "__main__":
    unittest.main()
