import unittest
from collections.abc import Mapping

from glio_noncode.errors import ValidationError
from glio_noncode.evidence_lifecycle import (
    CitationResolver,
    ClaimEvidenceEdgeValidator,
    ContradictionDisagreementTracker,
    DisagreementState,
    EvidenceCitation,
    EvidenceDossierPublisher,
    LifecycleState,
    VersionedEvidenceClaim,
    VersionedEvidenceGraphConstructor,
)


class EvidenceLifecycleTests(unittest.TestCase):
    CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"

    def _citation(
        self, citation_id: str, source_id: str, *, context_key: str | None = None
    ) -> EvidenceCitation:
        return EvidenceCitation(
            citation_id=citation_id,
            source_id=source_id,
            source_uri=f"https://example.test/{source_id}",
            title=f"Source {source_id}",
            version="v1",
            raw_hash=f"sha256:{source_id}",
            citation_text=f"{source_id}. Declared source.",
            retrieved_at="2026-08-20T00:00:00+00:00",
            context_key=context_key,
        )

    def _claim(
        self,
        claim_id: str,
        edge_id: str = "edge-1",
        source_id: str = "source-1",
        state: LifecycleState = LifecycleState.SUPPORTED,
        supersedes: str | None = None,
        parent_claim_ids: tuple[str, ...] = (),
        attributes: Mapping[str, object] | None = None,
    ) -> VersionedEvidenceClaim:
        return VersionedEvidenceClaim(
            claim_id=claim_id,
            edge_id=edge_id,
            context_key=self.CONTEXT,
            state=state,
            support=0.8,
            confidence=0.9,
            claim_type="functional",
            summary=f"Claim {claim_id}",
            source_ids=(source_id,),
            source_versions={source_id: "v1"},
            raw_hash=f"sha256:{claim_id}",
            parent_claim_ids=parent_claim_ids,
            supersedes=supersedes,
            attributes=dict(attributes or {}),
        )

    def test_citation_resolver_quarantines_malformed_rows_and_preserves_hashes(self) -> None:
        text = (
            "citation_id\tsource_uri\ttitle\tversion\tcitation_text\n"
            "c1\thttps://example.test/1\tOne\tv1\tOne citation\n"
            "c2\thttps://example.test/2\tTwo\tv1\t\n"
        )
        batch = CitationResolver().parse_text(text, source_id="manifest", source_version="v1")
        self.assertEqual(batch.state, LifecycleState.PARTIAL)
        self.assertEqual(len(batch.citations), 1)
        self.assertEqual(batch.quarantined_count, 1)
        self.assertTrue(batch.citations[0].raw_hash.startswith("sha256:"))
        self.assertEqual(batch.issues[0].code, "missing_required_field")

    def test_graph_is_append_only_replayable_and_retains_orphans(self) -> None:
        citations = (self._citation("citation-1", "source-1"),)
        first = self._claim("claim-1")
        replacement = self._claim("claim-2", supersedes="claim-1")
        orphan = self._claim(
            "claim-3", source_id="missing-source", parent_claim_ids=("missing-parent",)
        )
        graph = VersionedEvidenceGraphConstructor().construct(
            (first, replacement, orphan),
            citations=citations,
            context_key=self.CONTEXT,
            graph_id="graph-1",
        )
        self.assertEqual(graph.state, LifecycleState.PARTIAL)
        self.assertEqual(graph.superseded_claim_ids, ("claim-1",))
        self.assertEqual(graph.active_claim_ids, ("claim-2", "claim-3"))
        self.assertEqual(graph.orphan_claim_ids, ("claim-3",))
        self.assertEqual(graph.content_address, graph.replay().content_address)
        wrong_context = VersionedEvidenceClaim(
            claim_id="wrong",
            edge_id="edge-2",
            context_key="GRCh38|other|adult|stem_like|core|untreated",
            state=LifecycleState.SUPPORTED,
            support=0.5,
            confidence=0.5,
            claim_type="functional",
            summary="Wrong context",
            source_ids=("source-1",),
            source_versions={"source-1": "v1"},
            raw_hash="sha256:wrong",
        )
        with self.assertRaises(ValidationError):
            graph.append(wrong_context)

    def test_edge_validator_resolves_citations_and_reports_supported(self) -> None:
        claim = self._claim("claim-1")
        graph = VersionedEvidenceGraphConstructor().construct(
            (claim,),
            citations=(self._citation("citation-1", "source-1"),),
            context_key=self.CONTEXT,
        )
        report = ClaimEvidenceEdgeValidator().validate(
            graph, "edge-1", expected_context_key=self.CONTEXT
        )
        self.assertEqual(report.state, LifecycleState.SUPPORTED)
        self.assertEqual(report.missing_source_ids, ())
        self.assertFalse(report.contradiction)

    def test_contradiction_tracker_keeps_positive_and_negative_claims_separate(self) -> None:
        claims = (
            self._claim("positive", attributes={"claim_value": "increases"}),
            self._claim(
                "negative",
                source_id="source-2",
                state=LifecycleState.MEASURED_NEGATIVE,
                attributes={"claim_value": "decreases"},
            ),
        )
        graph = VersionedEvidenceGraphConstructor().construct(
            claims,
            citations=(
                self._citation("citation-1", "source-1"),
                self._citation("citation-2", "source-2"),
            ),
            context_key=self.CONTEXT,
        )
        report = ContradictionDisagreementTracker().track(graph)
        self.assertEqual(graph.state, LifecycleState.CONTRADICTORY)
        self.assertEqual(report.contradictory_edge_ids, ("edge-1",))
        record = report.records[0]
        self.assertEqual(record.state, DisagreementState.CONTRADICTORY)
        self.assertEqual(record.positive_claim_ids, ("positive",))
        self.assertEqual(record.negative_claim_ids, ("negative",))
        self.assertEqual(set(record.value_groups), {"decreases", "increases"})

    def test_citation_context_mismatch_is_out_of_domain(self) -> None:
        claim = self._claim("claim-1")
        graph = VersionedEvidenceGraphConstructor().construct(
            (claim,),
            citations=(
                self._citation(
                    "citation-1",
                    "source-1",
                    context_key="GRCh38|glioma|pediatric|stem_like|core|untreated",
                ),
            ),
            context_key=self.CONTEXT,
        )
        self.assertEqual(graph.state, LifecycleState.OUT_OF_DOMAIN)
        edge = ClaimEvidenceEdgeValidator().validate(graph, "edge-1")
        self.assertEqual(edge.state, LifecycleState.OUT_OF_DOMAIN)

    def test_dossier_is_review_required_and_content_addressed(self) -> None:
        graph = VersionedEvidenceGraphConstructor().construct(
            (self._claim("claim-1"),),
            citations=(self._citation("citation-1", "source-1"),),
            context_key=self.CONTEXT,
            graph_id="graph-1",
        )
        dossier = EvidenceDossierPublisher().publish(graph, dossier_id="dossier-1")
        self.assertEqual(dossier.release_state, "review_required")
        self.assertTrue(dossier.research_use_only)
        self.assertTrue(dossier.integrity_digest.startswith("sha256:"))
        self.assertEqual(
            dossier.content_address,
            EvidenceDossierPublisher().publish(graph, dossier_id="dossier-1").content_address,
        )


if __name__ == "__main__":
    unittest.main()
