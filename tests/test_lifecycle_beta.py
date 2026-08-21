from __future__ import annotations

import unittest

from glio_noncode.evidence_lifecycle import (
    EvidenceCitation,
    LifecycleState,
    VersionedEvidenceClaim,
    VersionedEvidenceGraphConstructor,
)
from glio_noncode.lifecycle_beta import (
    EvidenceTier,
    EvidenceTierAdjudicator,
    EvidenceTierObservation,
    LifecycleBetaState,
    ProvenanceLineageViewer,
    ReviewerAssignmentRouter,
    ReviewerRole,
    TierDirection,
    UncertaintyDimension,
    UncertaintyLedgerBuilder,
    UncertaintyObservation,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"
OTHER_CONTEXT = "GRCh38|glioma|pediatric|stem_like|core|untreated"


def citation(citation_id: str, source_id: str) -> EvidenceCitation:
    return EvidenceCitation(
        citation_id=citation_id,
        source_id=source_id,
        source_uri=f"https://example.test/{source_id}",
        title=source_id,
        version="v1",
        raw_hash=f"sha256:{source_id}",
        citation_text=f"Citation for {source_id}",
        retrieved_at="2026-08-21T00:00:00+00:00",
    )


def claim(
    claim_id: str,
    *,
    edge_id: str = "edge-1",
    source_id: str = "source-1",
    state: LifecycleState = LifecycleState.SUPPORTED,
    parent_claim_ids: tuple[str, ...] = (),
    supersedes: str | None = None,
    attributes: dict[str, object] | None = None,
) -> VersionedEvidenceClaim:
    return VersionedEvidenceClaim(
        claim_id=claim_id,
        edge_id=edge_id,
        context_key=CONTEXT,
        state=state,
        support=0.8,
        confidence=0.8,
        claim_type="functional",
        summary=f"Claim {claim_id}",
        source_ids=(source_id,),
        source_versions={source_id: "v1"},
        raw_hash=f"sha256:{claim_id}",
        parent_claim_ids=parent_claim_ids,
        supersedes=supersedes,
        attributes=attributes or {},
    )


def graph(*claims_to_use: VersionedEvidenceClaim):
    sources = tuple(
        citation(source_id, source_id)
        for source_id in sorted({source for item in claims_to_use for source in item.source_ids})
    )
    return VersionedEvidenceGraphConstructor().construct(
        claims_to_use,
        citations=sources,
        context_key=CONTEXT,
        graph_id="graph-beta",
    )


class LifecycleBetaTests(unittest.TestCase):
    def test_tier_adjudicator_preserves_highest_tier_and_conflict(self) -> None:
        result = EvidenceTierAdjudicator().adjudicate(
            (
                EvidenceTierObservation(
                    "tier-1",
                    "claim-1",
                    "edge-1",
                    CONTEXT,
                    EvidenceTier.CONTEXT_MATCHED_OBSERVATION,
                    TierDirection.SUPPORTS,
                    0.7,
                    0.8,
                    "atlas",
                    "v1",
                    "raw-tier-1",
                    "context-matched observation",
                ),
                EvidenceTierObservation(
                    "tier-2",
                    "claim-1",
                    "edge-1",
                    CONTEXT,
                    EvidenceTier.DIRECT_PERTURBATION,
                    TierDirection.AGAINST,
                    0.6,
                    0.7,
                    "perturbation",
                    "v1",
                    "raw-tier-2",
                    "direct perturbation disagrees",
                ),
                EvidenceTierObservation(
                    "tier-3",
                    "claim-2",
                    "edge-2",
                    CONTEXT,
                    EvidenceTier.UNCLASSIFIED,
                    TierDirection.SUPPORTS,
                    None,
                    0.4,
                    "unknown",
                    "v1",
                    "raw-tier-3",
                    "tier missing",
                ),
            ),
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, LifecycleBetaState.CONTRADICTORY)
        decision = result.decisions[0]
        self.assertEqual(decision.highest_tier, EvidenceTier.DIRECT_PERTURBATION)
        self.assertEqual(decision.state, LifecycleBetaState.CONTRADICTORY)
        self.assertEqual(set(decision.supporting_observation_ids), {"tier-1"})
        self.assertEqual(set(decision.against_observation_ids), {"tier-2"})

    def test_tier_adjudicator_reports_context_out_of_domain(self) -> None:
        result = EvidenceTierAdjudicator().adjudicate(
            (
                {
                    "observation_id": "other",
                    "claim_id": "claim-1",
                    "edge_id": "edge-1",
                    "context_key": OTHER_CONTEXT,
                    "tier": "computational_proxy",
                    "source_id": "model",
                    "rationale": "other context",
                },
            ),
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, LifecycleBetaState.OUT_OF_DOMAIN)
        self.assertEqual(result.decisions, ())

    def test_lineage_view_exposes_parent_supersession_source_and_citation_edges(self) -> None:
        snapshot = graph(
            claim("claim-1", source_id="source-1"),
            claim(
                "claim-2",
                source_id="source-2",
                parent_claim_ids=("claim-1",),
                supersedes="claim-1",
            ),
        )
        view = ProvenanceLineageViewer().view(snapshot, claim_id="claim-2")
        self.assertEqual(view.state, LifecycleBetaState.SUPPORTED)
        self.assertEqual(set(view.selected_claim_ids), {"claim-1", "claim-2"})
        self.assertIn("parent", {edge.relation for edge in view.edges})
        self.assertIn("supersedes", {edge.relation for edge in view.edges})
        self.assertIn("citation", {edge.relation for edge in view.edges})
        active_only = ProvenanceLineageViewer().view(
            snapshot, claim_id="claim-2", include_superseded=False
        )
        self.assertEqual(active_only.selected_claim_ids, ("claim-2",))
        self.assertEqual(active_only.omitted_claim_ids, ("claim-1",))

    def test_uncertainty_ledger_uses_conservative_dimension_maxima(self) -> None:
        result = UncertaintyLedgerBuilder().build(
            (
                UncertaintyObservation(
                    "u-1",
                    "claim-1",
                    "edge-1",
                    CONTEXT,
                    UncertaintyDimension.MEASUREMENT,
                    0.4,
                    "assay",
                    "v1",
                    "raw-u1",
                    "replicate spread",
                ),
                UncertaintyObservation(
                    "u-2",
                    "claim-1",
                    "edge-1",
                    CONTEXT,
                    UncertaintyDimension.TRANSPORT,
                    0.8,
                    "context-audit",
                    "v1",
                    "raw-u2",
                    "cell-state mismatch risk",
                ),
            ),
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, LifecycleBetaState.SUPPORTED)
        self.assertEqual(result.claims[0].uncertainty, 0.8)
        self.assertEqual(result.claims[0].top_dimension, "transport")
        self.assertEqual(result.top_drivers, ("claim-1:transport",))

    def test_reviewer_router_adds_roles_for_contradiction_and_uncertainty(self) -> None:
        snapshot = graph(
            claim("positive", source_id="source-1", attributes={"claim_value": "increases"}),
            claim(
                "negative",
                source_id="source-2",
                state=LifecycleState.MEASURED_NEGATIVE,
                attributes={"claim_value": "decreases"},
            ),
        )
        uncertainty = UncertaintyLedgerBuilder().build(
            (
                {
                    "observation_id": "uncertainty-1",
                    "claim_id": "positive",
                    "edge_id": "edge-1",
                    "context_key": CONTEXT,
                    "dimension": "measurement",
                    "value": 0.7,
                    "source_id": "assay",
                    "rationale": "replicate spread",
                },
            ),
            context_key=CONTEXT,
        )
        result = ReviewerAssignmentRouter().route(
            snapshot,
            uncertainty=uncertainty,
            required_roles=(ReviewerRole.DATA_PROVENANCE,),
        )
        self.assertEqual(result.state, LifecycleBetaState.CONTRADICTORY)
        self.assertEqual(len(result.assignments), 2)
        assignment = result.assignments[0]
        self.assertIn(ReviewerRole.STATISTICAL_REVIEW, assignment.roles)
        self.assertIn(ReviewerRole.DOMAIN_EXPERT, assignment.roles)
        self.assertGreaterEqual(assignment.priority, 0.7)
        self.assertEqual(result.unassigned_claim_ids, ())


if __name__ == "__main__":
    unittest.main()
