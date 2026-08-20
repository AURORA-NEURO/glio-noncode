from __future__ import annotations

import unittest

from glio_noncode.atlas import AtlasQuery, PublicAtlasRetriever
from glio_noncode.data_sources import (
    FetchReceipt,
    FetchStatus,
    ReferenceBundle,
    SequenceSlice,
    SourcePayload,
)
from glio_noncode.identity import parse_variant
from glio_noncode.models import EvidenceState, ReferenceContext
from glio_noncode.serialization import content_hash


def _receipt(source_id: str, suffix: str) -> FetchReceipt:
    return FetchReceipt(
        source_id=source_id,
        source_version="fixture-1",
        url=f"https://{source_id.lower()}.example/{suffix}",
        request_hash=f"sha256:req-{suffix}",
        response_hash=f"sha256:resp-{suffix}",
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="2026-08-20T00:00:00+00:00",
        elapsed_seconds=0.01,
        cache_expires_at=None,
    )


class StubReferenceRetriever:
    def retrieve(self, variant, context, *, window_bp=None):
        self.window_bp = window_bp
        sequence = SequenceSlice(
            assembly=context.genome_build,
            chromosome=variant.chromosome,
            start=variant.start,
            end=variant.start + 3,
            sequence="ACGT",
            source_id="SRC-UCSC-REST",
            receipt=_receipt("SRC-UCSC-REST", "sequence"),
        )
        raw_features = ({"feature_type": "gene", "id": "ENSG000001", "external_name": "GENE_A"},)
        return ReferenceBundle(
            variant_id=variant.variant_id,
            context_key=context.key,
            sequence=sequence,
            elements=(),
            raw_features=raw_features,
            receipts=(sequence.receipt, _receipt("SRC-ENSEMBL-REST", "overlap")),
            warnings=(),
            content_address=content_hash({"variant_id": variant.variant_id}),
        )


class StubEncodeClient:
    def search_experiments(
        self,
        *,
        assay_title=None,
        biosample_ontology_term_name=None,
        organism="Homo sapiens",
        limit=25,
    ):
        return SourcePayload(
            {"@graph": [{"accession": "ENCSR000AAA", "assay_title": assay_title or "ATAC-seq"}]},
            _receipt("SRC-ENCODE-REST", "search"),
            "application/json",
        )


class AtlasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.variant = parse_variant("7:100:A>T", genome_build="GRCh38", variant_id="v1")
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")

    def test_public_atlas_preserves_sequence_feature_and_encode_observations(self) -> None:
        reference = StubReferenceRetriever()
        atlas = PublicAtlasRetriever(reference, StubEncodeClient()).retrieve(
            self.variant,
            self.context,
            query=AtlasQuery(
                variant_id="v1",
                window_bp=25,
                include_encode_catalog=True,
                encode_assay_title="ATAC-seq",
            ),
        )
        self.assertEqual(reference.window_bp, 25)
        self.assertEqual(
            {observation.source_id for observation in atlas.observations},
            {
                "SRC-UCSC-REST",
                "SRC-ENSEMBL-REST",
                "SRC-ENCODE-REST",
            },
        )
        self.assertEqual(atlas.abstained_count, 0)
        self.assertIsNotNone(atlas.sequence_analysis)
        self.assertIsNotNone(atlas.uncertainty)
        claims = atlas.to_evidence_claims(variant=self.variant, context=self.context)
        self.assertEqual(len(claims), len(atlas.observations))
        self.assertTrue(all(claim.score is None for claim in claims))

    def test_no_feature_overlap_is_absent_not_a_disease_negative(self) -> None:
        reference = StubReferenceRetriever()
        bundle = reference.retrieve(self.variant, self.context, window_bp=10)
        empty_bundle = ReferenceBundle(
            variant_id=bundle.variant_id,
            context_key=bundle.context_key,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=bundle.receipts,
            warnings=("feature retrieval returned no rows",),
            content_address=content_hash({"empty": True}),
        )

        class EmptyReference:
            def retrieve(self, variant, context, *, window_bp=None):
                return empty_bundle

        atlas = PublicAtlasRetriever(EmptyReference()).retrieve(self.variant, self.context)
        states = {observation.feature_type: observation.state for observation in atlas.observations}
        self.assertEqual(states["reference_sequence"], EvidenceState.ABSTAINED)
        self.assertEqual(states["reference_annotation"], EvidenceState.ABSENT)
        self.assertIn("not a negative", atlas.observations[-1].limitations[0])


if __name__ == "__main__":
    unittest.main()
