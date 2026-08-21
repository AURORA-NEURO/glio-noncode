from __future__ import annotations

import unittest

from glio_noncode.evidence_lifecycle import (
    EvidenceCitation,
    LifecycleState,
    VersionedEvidenceClaim,
    VersionedEvidenceGraphConstructor,
)
from glio_noncode.lifecycle_alpha import (
    AdjudicationVerdict,
    BlindedAdjudicationWorkflow,
    EvidenceDeltaDetector,
    LifecycleAlphaState,
    ReleaseDecision,
    ReleaseDecisionRecorder,
    ReviewerCommentChangeLogger,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class LifecycleAlphaTests(unittest.TestCase):
    def _citation(
        self, citation_id: str, source_id: str, title: str = "Source"
    ) -> EvidenceCitation:
        return EvidenceCitation(
            citation_id=citation_id,
            source_id=source_id,
            source_uri=f"https://example.test/{source_id}",
            title=title,
            version="v1",
            raw_hash=f"sha256:{source_id}",
            citation_text=f"Declared evidence from {source_id}",
            retrieved_at="2026-08-21T00:00:00+00:00",
        )

    def _claim(
        self, claim_id: str, source_id: str, summary: str | None = None
    ) -> VersionedEvidenceClaim:
        return VersionedEvidenceClaim(
            claim_id=claim_id,
            edge_id=f"edge-{claim_id}",
            context_key=CONTEXT,
            state=LifecycleState.SUPPORTED,
            support=0.8,
            confidence=0.9,
            claim_type="functional",
            summary=summary or f"Claim {claim_id}",
            source_ids=(source_id,),
            source_versions={source_id: "v1"},
            raw_hash=f"sha256:{claim_id}",
        )

    def _graph(
        self, claims: tuple[VersionedEvidenceClaim, ...], citations: tuple[EvidenceCitation, ...]
    ):
        return VersionedEvidenceGraphConstructor().construct(
            claims,
            citations=citations,
            graph_id="alpha-graph",
            context_key=CONTEXT,
        )

    def test_blinded_workflow_masks_sources_and_reconciles_consensus(self) -> None:
        workflow = BlindedAdjudicationWorkflow()
        plan = workflow.plan(
            [
                {
                    "observation_id": "obs-1",
                    "claim_id": "claim-1",
                    "edge_id": "edge-1",
                    "context_key": CONTEXT,
                    "evidence_digest": "sha256:evidence-1",
                    "source_ids": ["source-a", "source-b"],
                    "source_versions": {"source-a": "v1", "source-b": "v2"},
                }
            ],
            workflow_id="workflow-1",
            context_key=CONTEXT,
            reviewer_count=2,
            randomization_seed="fixed",
        )
        self.assertEqual(plan.state, LifecycleAlphaState.READY_FOR_REVIEW)
        packet = plan.to_dict()
        self.assertNotIn("_claim_id", packet)
        self.assertNotIn("source-a", str(packet))
        case = plan.cases[0]
        result = workflow.adjudicate(
            plan,
            [
                {
                    "decision_id": "d-1",
                    "case_id": case.case_id,
                    "reviewer_token": plan.reviewer_tokens[0],
                    "verdict": "supports",
                    "confidence": 0.8,
                    "rationale": "evidence supports the declared direction",
                    "context_key": CONTEXT,
                },
                {
                    "decision_id": "d-2",
                    "case_id": case.case_id,
                    "reviewer_token": plan.reviewer_tokens[1],
                    "verdict": "supports",
                    "confidence": 0.7,
                    "rationale": "independent masked review supports",
                    "context_key": CONTEXT,
                },
            ],
        )
        self.assertEqual(result.state, LifecycleAlphaState.ADJUDICATED)
        self.assertEqual(result.cases[0].verdicts, (AdjudicationVerdict.SUPPORTS,) * 2)
        self.assertEqual(result.cases[0].agreement, 1.0)

    def test_blinded_workflow_preserves_split_decision_and_context_blocker(self) -> None:
        workflow = BlindedAdjudicationWorkflow()
        plan = workflow.plan(
            [
                {
                    "observation_id": "obs-1",
                    "claim_id": "claim-1",
                    "edge_id": "edge-1",
                    "context_key": CONTEXT,
                    "evidence_digest": "sha256:evidence-1",
                    "source_id": "source-a",
                },
                {
                    "observation_id": "obs-2",
                    "claim_id": "claim-2",
                    "edge_id": "edge-2",
                    "context_key": "other-context",
                    "evidence_digest": "sha256:evidence-2",
                    "source_id": "source-b",
                },
            ],
            context_key=CONTEXT,
            reviewer_count=2,
        )
        self.assertEqual(plan.state, LifecycleAlphaState.READY_FOR_REVIEW)
        case = plan.cases[0]
        result = workflow.adjudicate(
            plan,
            [
                {
                    "decision_id": "d-1",
                    "case_id": case.case_id,
                    "reviewer_token": plan.reviewer_tokens[0],
                    "verdict": "supports",
                    "confidence": 0.8,
                    "rationale": "support",
                    "context_key": CONTEXT,
                },
                {
                    "decision_id": "d-2",
                    "case_id": case.case_id,
                    "reviewer_token": plan.reviewer_tokens[1],
                    "verdict": "against",
                    "confidence": 0.8,
                    "rationale": "against",
                    "context_key": CONTEXT,
                },
            ],
        )
        self.assertEqual(result.state, LifecycleAlphaState.SPLIT_DECISION)
        self.assertEqual(len(plan.issues), 1)
        self.assertEqual(plan.issues[0].code, "context_mismatch")

    def test_reviewer_log_is_append_only_and_content_addressed(self) -> None:
        logger = ReviewerCommentChangeLogger()
        log = logger.record(
            comments=[
                {
                    "comment_id": "comment-1",
                    "review_id": "review-1",
                    "target_type": "claim",
                    "target_id": "claim-1",
                    "context_key": CONTEXT,
                    "author_role": "domain_expert",
                    "text": "Confirm source context before release.",
                }
            ],
            changes=[
                {
                    "change_id": "change-1",
                    "review_id": "review-1",
                    "target_type": "claim",
                    "target_id": "claim-1",
                    "context_key": CONTEXT,
                    "actor_role": "domain_expert",
                    "action": "add_condition",
                    "before_hash": "sha256:before",
                    "after_hash": "sha256:after",
                    "rationale": "make the unresolved context explicit",
                }
            ],
            review_id="review-1",
            context_key=CONTEXT,
        )
        self.assertEqual(log.state, LifecycleAlphaState.READY_FOR_REVIEW)
        appended = logger.append(
            log,
            comments=[
                {
                    "comment_id": "comment-2",
                    "review_id": "review-1",
                    "target_type": "claim",
                    "target_id": "claim-1",
                    "context_key": CONTEXT,
                    "author_role": "data_provenance",
                    "text": "Citation version is retained.",
                }
            ],
        )
        self.assertEqual(len(log.comments), 1)
        self.assertEqual(len(appended.comments), 2)
        self.assertNotEqual(log.content_address, appended.content_address)

    def test_release_decision_requires_explicit_gates_and_delta_detects_changes(self) -> None:
        previous = self._graph(
            (self._claim("claim-1", "source-1"),),
            (self._citation("citation-1", "source-1"),),
        )
        approved = ReleaseDecisionRecorder().record(
            previous,
            [
                {
                    "gate_id": "gate-citations",
                    "label": "citation coverage",
                    "passed": True,
                    "blocking": True,
                    "context_key": CONTEXT,
                    "evidence_hash": "sha256:gate",
                    "reason": "all citations resolved",
                    "source_id": "audit",
                }
            ],
            release_id="release-1",
            required_roles=("domain_expert", "data_provenance"),
            completed_roles=("domain_expert", "data_provenance"),
            reviewer_ids=("reviewer-1",),
            requested_decision=ReleaseDecision.APPROVED,
        )
        self.assertEqual(approved.state, LifecycleAlphaState.APPROVED)
        self.assertTrue(approved.research_use_only)
        conditional = ReleaseDecisionRecorder().record(
            previous,
            [{"gate_id": "gate-fail", "label": "required", "passed": False}],
            release_id="release-2",
        )
        self.assertEqual(conditional.decision, ReleaseDecision.REVIEW_REQUIRED)
        current = self._graph(
            (
                self._claim("claim-1", "source-1", summary="changed claim"),
                self._claim("claim-2", "source-2"),
            ),
            (
                self._citation("citation-1", "source-1"),
                self._citation("citation-2", "source-2"),
            ),
        )
        delta = EvidenceDeltaDetector().compare(previous, current, expected_context_key=CONTEXT)
        self.assertEqual(delta.state, LifecycleAlphaState.REVIEW_REQUIRED)
        self.assertEqual(delta.added_claim_count, 1)
        self.assertEqual(delta.changed_claim_count, 1)
        self.assertEqual(delta.added_citation_count, 1)
        self.assertTrue(delta.review_required)


if __name__ == "__main__":
    unittest.main()
