from __future__ import annotations

import unittest

from glio_noncode.atlas_alpha_evidence_fixture_eval import evaluate_atlas_alpha_evidence_fixture
from glio_noncode.atlas_alpha_evidence_lineage import (
    build_atlas_alpha_evidence_lineage,
    verify_atlas_alpha_evidence_lineage,
)
from glio_noncode.atlas_alpha_evidence_metrics import compute_atlas_alpha_evidence_metrics
from glio_noncode.atlas_alpha_evidence_policy import evaluate_atlas_alpha_evidence_policy
from glio_noncode.atlas_alpha_evidence_public_data import (
    ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
    AtlasAlphaEvidenceOperation,
    AtlasAlphaEvidenceRole,
    audit_atlas_alpha_evidence_data,
    build_atlas_alpha_evidence_catalog,
    default_atlas_alpha_evidence_fixture,
)
from glio_noncode.atlas_alpha_evidence_quality_gate import run_atlas_alpha_evidence_quality_gate
from glio_noncode.atlas_alpha_evidence_reconciliation import reconcile_atlas_alpha_evidence
from glio_noncode.atlas_alpha_evidence_release import build_atlas_alpha_evidence_release
from glio_noncode.atlas_alpha_evidence_replay import replay_atlas_alpha_evidence_evaluation
from glio_noncode.atlas_alpha_evidence_runtime import (
    AtlasAlphaEvidenceRuntimeOptions,
    run_atlas_alpha_evidence_pipeline,
)
from glio_noncode.atlas_alpha_evidence_scenario_matrix import (
    evaluate_atlas_alpha_evidence_scenarios,
)


class AtlasAlphaEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_atlas_alpha_evidence_fixture()
        self.evaluation = evaluate_atlas_alpha_evidence_fixture(self.fixture)

    def test_public_fixture_is_balanced_and_source_closed(self) -> None:
        self.assertEqual(self.fixture.context_key, ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(audit_atlas_alpha_evidence_data(self.fixture).accepted)
        catalog = build_atlas_alpha_evidence_catalog(self.fixture)
        self.assertEqual(set(catalog.operations), set(AtlasAlphaEvidenceOperation))
        self.assertEqual(len(catalog.record_ids), 16)

    def test_evaluation_has_exact_states_and_one_hundred_twenty_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.positive_count, 4)
        self.assertEqual(self.evaluation.control_count, 12)
        self.assertEqual(
            tuple(
                (receipt.record_id, receipt.adapter_state) for receipt in self.evaluation.receipts
            ),
            (
                ("C09-POS-001", "supported"),
                ("C09-CTRL-001", "partial"),
                ("C09-CTRL-002", "ambiguous"),
                ("C09-CTRL-003", "out_of_domain"),
                ("C10-POS-001", "supported"),
                ("C10-CTRL-001", "partial"),
                ("C10-CTRL-002", "ambiguous"),
                ("C10-CTRL-003", "out_of_domain"),
                ("C11-POS-001", "supported"),
                ("C11-CTRL-001", "partial"),
                ("C11-CTRL-002", "ambiguous"),
                ("C11-CTRL-003", "out_of_domain"),
                ("C12-POS-001", "supported"),
                ("C12-CTRL-001", "abstained"),
                ("C12-CTRL-002", "partial"),
                ("C12-CTRL-003", "out_of_domain"),
            ),
        )

    def test_replay_scenarios_policy_lineage_and_reconciliation_accept(self) -> None:
        replay = replay_atlas_alpha_evidence_evaluation(self.evaluation, fixture=self.fixture)
        self.assertTrue(replay.accepted)
        self.assertTrue(evaluate_atlas_alpha_evidence_scenarios(self.evaluation).accepted)
        self.assertTrue(
            evaluate_atlas_alpha_evidence_policy(self.fixture, self.evaluation).accepted
        )
        lineage = build_atlas_alpha_evidence_lineage(self.fixture, self.evaluation)
        self.assertFalse(
            verify_atlas_alpha_evidence_lineage(lineage, self.fixture, self.evaluation)
        )
        self.assertTrue(reconcile_atlas_alpha_evidence(self.fixture, self.evaluation).accepted)

    def test_quality_runtime_metrics_and_release_are_addressed(self) -> None:
        quality = run_atlas_alpha_evidence_quality_gate(self.fixture)
        self.assertTrue(quality.accepted)
        self.assertGreaterEqual(len(quality.checks), 11)
        metrics = compute_atlas_alpha_evidence_metrics(self.evaluation)
        self.assertEqual(metrics.total_records, 16)
        self.assertEqual(metrics.supported_records, 4)
        self.assertEqual(metrics.review_records, 12)
        self.assertEqual(len(metrics.operation_metrics), 4)
        runtime = run_atlas_alpha_evidence_pipeline(
            AtlasAlphaEvidenceRuntimeOptions(run_id="test-run"), fixture=self.fixture
        )
        self.assertTrue(runtime.accepted)
        release = build_atlas_alpha_evidence_release(quality, runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(
            set(release.operation_ids),
            {operation.value for operation in AtlasAlphaEvidenceOperation},
        )

    def test_fail_on_review_is_explicit_runtime_policy(self) -> None:
        result = run_atlas_alpha_evidence_pipeline(
            AtlasAlphaEvidenceRuntimeOptions(run_id="strict-run", fail_on_review=True),
            fixture=self.fixture,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.status, "rejected")

    def test_receipts_are_sanitized(self) -> None:
        for receipt in self.evaluation.receipts:
            self.assertNotIn("input_text", receipt.summary)
            self.assertNotIn("payload", receipt.summary)
            self.assertTrue(receipt.content_address.startswith("sha256:"))
            self.assertEqual(receipt.context_key, ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY)
            self.assertIn(
                receipt.role, (AtlasAlphaEvidenceRole.POSITIVE, AtlasAlphaEvidenceRole.CONTROL)
            )


if __name__ == "__main__":
    unittest.main()
