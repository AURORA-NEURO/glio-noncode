from __future__ import annotations

import unittest

from glio_noncode.evidence_release_frontier_contracts import EvidenceReleaseOperation, EvidenceReleaseRole, EvidenceReleaseState
from glio_noncode.evidence_release_frontier_fixture_eval import audit_evidence_release_context, evaluate_evidence_release_fixture
from glio_noncode.evidence_release_frontier_operations import evaluate_reclassification, evaluate_reproducibility_bundle, evaluate_supersession, sign_dossier, verify_signed_dossier
from glio_noncode.evidence_release_frontier_public_data import audit_evidence_release_frontier_data, default_evidence_release_frontier_fixture
from glio_noncode.evidence_release_frontier_runtime import run_evidence_release_runtime


class EvidenceReleaseFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_evidence_release_frontier_fixture()
        cls.audit = audit_evidence_release_frontier_data(cls.fixture)
        cls.evaluation = evaluate_evidence_release_fixture(cls.fixture)

    def test_public_fixture_shape_and_context(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(audit_evidence_release_context(self.fixture), ("GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment",))

    def test_every_row_has_five_planes_and_positive_dossier_has_verification(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 81)
        self.assertEqual(self.evaluation.failed_checks, 0)
        dossier = next(item for item in self.evaluation.executions if item.operation == EvidenceReleaseOperation.SIGNED_DOSSIER and item.role == EvidenceReleaseRole.POSITIVE)
        self.assertTrue(dossier.output["signature_verified"])

    def test_positive_states_are_explicit(self) -> None:
        expected = {EvidenceReleaseOperation.RECLASSIFICATION: EvidenceReleaseState.RECLASSIFIED, EvidenceReleaseOperation.SUPERSESSION: EvidenceReleaseState.SUPERSEDED, EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE: EvidenceReleaseState.BUNDLED, EvidenceReleaseOperation.SIGNED_DOSSIER: EvidenceReleaseState.SIGNED}
        for record in self.fixture.positive_records:
            result = __import__("glio_noncode.evidence_release_frontier_operations", fromlist=["run_evidence_release_operation"]).run_evidence_release_operation(record.operation, record.payload)
            self.assertEqual(result.state, expected[record.operation])
            self.assertEqual(result.issue_codes, ())

    def test_controls_keep_declared_boundaries(self) -> None:
        for record in self.fixture.control_records:
            execution = next(item for item in self.evaluation.executions if item.record_id == record.record_id)
            self.assertEqual(execution.observed_state, record.expected_state)
            self.assertTrue(set(record.expected_issue_codes) <= set(execution.issue_codes))

    def test_reclassification_requires_independent_review(self) -> None:
        positive = self.fixture.records[0].payload
        result = evaluate_reclassification(positive | {"reviewer_ids": ["reviewer-a"]})
        self.assertEqual(result.state, EvidenceReleaseState.REVIEW)
        self.assertIn("independent_reviewers_missing", result.issue_codes)

    def test_foreign_context_is_blocked_for_all_operations(self) -> None:
        for record in self.fixture.records:
            if record.role != EvidenceReleaseRole.POSITIVE:
                continue
            payload = dict(record.payload)
            payload["context_key"] = "GRCh38|foreign|context"
            if record.operation == EvidenceReleaseOperation.SUPERSESSION:
                payload["records"] = [{**payload["records"][0], "context_key": "GRCh38|foreign|context"}]
            if record.operation == EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE:
                payload["sections"] = [{**payload["sections"][0], "context_key": "GRCh38|foreign|context"}]
            result = __import__("glio_noncode.evidence_release_frontier_operations", fromlist=["run_evidence_release_operation"]).run_evidence_release_operation(record.operation, payload)
            self.assertEqual(result.state, EvidenceReleaseState.BLOCKED)

    def test_supersession_cycle_and_bundle_identity_are_visible(self) -> None:
        cycle = {"context_key": self.fixture.context_key, "records": [{"record_id": "a", "status": "active", "supersedes": "b", "context_key": self.fixture.context_key}, {"record_id": "b", "status": "deprecated", "supersedes": "a", "context_key": self.fixture.context_key}]}
        self.assertIn("supersession_cycle", evaluate_supersession(cycle).issue_codes)
        bundle = self.fixture.records[8].payload
        sections = list(bundle["sections"])
        sections[1] = {**sections[1], "section_id": sections[0]["section_id"]}
        self.assertIn("duplicate_section_id", evaluate_reproducibility_bundle(bundle | {"sections": sections}).issue_codes)

    def test_signed_dossier_is_verified_without_key_output(self) -> None:
        signed = sign_dossier(self.fixture.records[12].payload)
        self.assertEqual(signed.state, EvidenceReleaseState.SIGNED)
        verification = verify_signed_dossier({"signed_dossier": signed.output})
        self.assertEqual(verification.state, EvidenceReleaseState.VERIFIED)
        serialized = str(signed.to_dict()).lower()
        self.assertNotIn("verification-material", serialized)
        self.assertNotIn("signing_key", serialized)

    def test_runtime_closes_every_release_plane(self) -> None:
        runtime = run_evidence_release_runtime(self.fixture, run_id="frontier-test")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 53)
        self.assertEqual(runtime.stage_ids[0], "data-audit")
        self.assertEqual(runtime.stage_ids[-1], "observability")
        self.assertTrue(runtime.replay.deterministic)
        self.assertTrue(runtime.release.accepted)
        self.assertTrue(runtime.bundle.accepted)


if __name__ == "__main__":
    unittest.main()
