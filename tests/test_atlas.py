from __future__ import annotations

import unittest

import glio_noncode.atlas as atlas_module
from glio_noncode.atlas import (
    AtlasBundle,
    AtlasObservation,
    AtlasQuery,
    PublicAtlasRetriever,
)
from glio_noncode.data_sources import (
    FetchReceipt,
    FetchStatus,
    ReferenceBundle,
    SequenceSlice,
    SourcePayload,
)
from glio_noncode.errors import SourceError, ValidationError
from glio_noncode.identity import parse_variant
from glio_noncode.models import CandidateElement, EvidenceState, ReferenceContext
from glio_noncode.reference_manifest import ReferenceAccessMode
from glio_noncode.reference_registry import CoordinateSystem
from glio_noncode.reference_track_adapters import (
    DeclaredReferenceTrackAdapter,
    ReferenceTrackAdapterRegistry,
    ReferenceTrackMetadata,
    ReferenceTrackQueryState,
)
from glio_noncode.sequence_inference import (
    MotifDefinition,
    SequenceAnalysisState,
    SequenceInference,
)
from glio_noncode.serialization import content_hash
from glio_noncode.uncertainty import DomainProfile


def _receipt(source_id: str, suffix: str) -> FetchReceipt:
    return FetchReceipt(
        source_id=source_id,
        source_version="fixture-1",
        url=f"https://{source_id.lower()}.example/{suffix}",
        request_hash=content_hash({"request": suffix, "source_id": source_id}),
        response_hash=content_hash({"response": suffix, "source_id": source_id}),
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="2026-08-20T00:00:00+00:00",
        elapsed_seconds=0.01,
        cache_expires_at=None,
    )


def _failed_receipt(source_id: str, suffix: str) -> FetchReceipt:
    return FetchReceipt(
        source_id=source_id,
        source_version="fixture-1",
        url=f"https://{source_id.lower()}.example/{suffix}",
        request_hash=content_hash({"request": suffix, "source_id": source_id}),
        response_hash=None,
        status=FetchStatus.FAILED,
        http_status=None,
        attempts=1,
        retrieved_at="2026-08-20T00:00:00+00:00",
        elapsed_seconds=0.01,
        cache_expires_at=None,
        error_type="SourceError",
        error_message="fixture source failed",
    )


class FixedReference:
    def __init__(self, bundle: ReferenceBundle) -> None:
        self.bundle = bundle

    def retrieve(self, variant, context, *, window_bp=None):
        self.window_bp = window_bp
        return self.bundle


class FixedEncodeClient:
    def __init__(
        self, value, *, source_id: str = "SRC-ENCODE-REST", content_type: str = "application/json"
    ) -> None:
        self.payload = SourcePayload(value, _receipt(source_id, "encode"), content_type)

    def search_experiments(
        self,
        *,
        assay_title=None,
        biosample_ontology_term_name=None,
        organism="Homo sapiens",
        limit=25,
    ):
        self.limit = limit
        return self.payload


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
        return ReferenceBundle.create(
            variant_id=variant.variant_id,
            context_key=context.key,
            sequence=sequence,
            elements=(),
            raw_features=raw_features,
            receipts=(sequence.receipt, _receipt("SRC-ENSEMBL-REST", "overlap")),
            warnings=(),
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
        empty_bundle = ReferenceBundle.create(
            variant_id=bundle.variant_id,
            context_key=bundle.context_key,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=bundle.receipts,
            warnings=("feature retrieval returned no rows",),
        )

        class EmptyReference:
            def retrieve(self, variant, context, *, window_bp=None):
                return empty_bundle

        atlas = PublicAtlasRetriever(EmptyReference()).retrieve(self.variant, self.context)
        states = {observation.feature_type: observation.state for observation in atlas.observations}
        self.assertEqual(states["reference_sequence"], EvidenceState.ABSTAINED)
        self.assertEqual(states["reference_annotation"], EvidenceState.ABSENT)
        annotation = next(
            item for item in atlas.observations if item.feature_type == "reference_annotation"
        )
        self.assertIn("not a negative", annotation.limitations[0])

    def test_feature_failure_abstains_while_successful_empty_is_absent(self) -> None:
        original = StubReferenceRetriever().retrieve(self.variant, self.context, window_bp=10)
        failed = ReferenceBundle.create(
            variant_id=original.variant_id,
            context_key=original.context_key,
            sequence=original.sequence,
            elements=(),
            raw_features=(),
            receipts=original.receipts,
            warnings=("feature retrieval abstained: malformed Ensembl response",),
        )
        result = PublicAtlasRetriever(FixedReference(failed)).retrieve(
            self.variant,
            self.context,
        )
        observation = next(
            item for item in result.observations if item.feature_type == "reference_annotation"
        )
        self.assertEqual(observation.state, EvidenceState.ABSTAINED)
        self.assertIn("not evidence", observation.limitations[0])

        successful = ReferenceBundle.create(
            variant_id=original.variant_id,
            context_key=original.context_key,
            sequence=original.sequence,
            elements=(),
            raw_features=(),
            receipts=original.receipts,
            warnings=(),
        )
        result = PublicAtlasRetriever(FixedReference(successful)).retrieve(
            self.variant,
            self.context,
        )
        observation = next(
            item for item in result.observations if item.feature_type == "reference_annotation"
        )
        self.assertEqual(observation.state, EvidenceState.ABSENT)

    def test_reference_bundle_identity_context_and_address_are_closed(self) -> None:
        bundle = StubReferenceRetriever().retrieve(self.variant, self.context, window_bp=25)
        other_variant = parse_variant(
            "7:101:C>T",
            genome_build="GRCh38",
            variant_id="other",
        )
        with self.assertRaisesRegex(ValidationError, "variant_id"):
            PublicAtlasRetriever(FixedReference(bundle)).retrieve(other_variant, self.context)

        other_context = ReferenceContext("GRCh38", "glioma", "adult", "astrocyte")
        with self.assertRaisesRegex(ValidationError, "context"):
            PublicAtlasRetriever(FixedReference(bundle)).retrieve(self.variant, other_context)

        object.__setattr__(bundle, "content_address", "sha256:" + "0" * 64)
        with self.assertRaisesRegex(ValidationError, "content_address"):
            PublicAtlasRetriever(FixedReference(bundle)).retrieve(self.variant, self.context)

    def test_same_id_bundle_cannot_substitute_contig_window_or_full_context(self) -> None:
        wrong_contig_receipt = _receipt("SRC-UCSC-REST", "wrong-contig")
        wrong_contig_sequence = SequenceSlice(
            assembly="GRCh38",
            chromosome="chr8",
            start=100,
            end=103,
            sequence="ACGT",
            source_id="SRC-UCSC-REST",
            receipt=wrong_contig_receipt,
        )
        wrong_contig = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context_key=self.context.key,
            sequence=wrong_contig_sequence,
            elements=(),
            raw_features=(),
            receipts=(wrong_contig_receipt,),
            warnings=(),
        )
        with self.assertRaisesRegex(ValidationError, "chromosome"):
            PublicAtlasRetriever(FixedReference(wrong_contig)).retrieve(
                self.variant,
                self.context,
            )

        displaced_receipt = _receipt("SRC-UCSC-REST", "wrong-window")
        displaced_sequence = SequenceSlice(
            assembly="GRCh38",
            chromosome=self.variant.chromosome,
            start=1_000,
            end=1_003,
            sequence="ACGT",
            source_id="SRC-UCSC-REST",
            receipt=displaced_receipt,
        )
        displaced = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context_key=self.context.key,
            sequence=displaced_sequence,
            elements=(),
            raw_features=(),
            receipts=(displaced_receipt,),
            warnings=(),
        )
        with self.assertRaisesRegex(ValidationError, "cover"):
            PublicAtlasRetriever(FixedReference(displaced)).retrieve(
                self.variant,
                self.context,
            )

        substituted_context = ReferenceContext(
            "GRCh38",
            "glioma",
            "adult",
            "stem_like",
            source_version="substituted",
        )
        element = CandidateElement(
            element_id="element-1",
            chromosome=self.variant.chromosome,
            start=100,
            end=100,
            element_type="regulatory",
            context=substituted_context,
            source_id="SRC-ENSEMBL-REST",
            target_genes=("GENE_A",),
        )
        element_bundle = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context_key=self.context.key,
            sequence=None,
            elements=(element,),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        with self.assertRaisesRegex(ValidationError, "exactly match"):
            PublicAtlasRetriever(FixedReference(element_bundle)).retrieve(
                self.variant,
                self.context,
            )

    def test_overlapping_features_may_span_beyond_the_query_window(self) -> None:
        receipt = _receipt("SRC-ENSEMBL-REST", "spanning-feature")
        element = CandidateElement(
            element_id="spanning-element",
            chromosome=self.variant.chromosome,
            start=50,
            end=150,
            element_type="regulatory",
            context=self.context,
            source_id="SRC-ENSEMBL-REST",
            target_genes=("GENE_A",),
        )
        bundle = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context_key=self.context.key,
            sequence=None,
            elements=(element,),
            raw_features=(
                {
                    "feature_type": "regulatory",
                    "id": "spanning-element",
                    "seq_region_name": self.variant.chromosome,
                    "start": 50,
                    "end": 150,
                },
            ),
            receipts=(receipt,),
            warnings=(),
        )
        result = PublicAtlasRetriever(FixedReference(bundle)).retrieve(
            self.variant,
            self.context,
            query=AtlasQuery(variant_id=self.variant.variant_id, window_bp=25),
        )
        observation = next(
            item for item in result.observations if item.feature_type == "reference_regulatory"
        )
        self.assertEqual(observation.state, EvidenceState.SUPPORTED)

    def test_encode_malformed_and_overlimit_payloads_abstain(self) -> None:
        cases = (
            ({"@graph": "not-an-array"}, 25),
            ({"@graph": [{"accession": "A"}, {"accession": "B"}]}, 1),
        )
        for value, limit in cases:
            with self.subTest(value=value, limit=limit):
                result = PublicAtlasRetriever(
                    StubReferenceRetriever(),
                    FixedEncodeClient(value),
                ).retrieve(
                    self.variant,
                    self.context,
                    query=AtlasQuery(
                        variant_id=self.variant.variant_id,
                        include_encode_catalog=True,
                        encode_limit=limit,
                    ),
                )
                observation = next(
                    item for item in result.observations if item.feature_type == "assay_catalog"
                )
                self.assertEqual(observation.state, EvidenceState.ABSTAINED)
                self.assertTrue(any("payload abstained" in item for item in result.warnings))
                self.assertIn(observation.receipt, result.receipts)

    def test_encode_successful_empty_is_absent_and_wrong_source_is_rejected(self) -> None:
        result = PublicAtlasRetriever(
            StubReferenceRetriever(),
            FixedEncodeClient({"@graph": [], "facets": []}),
        ).retrieve(
            self.variant,
            self.context,
            query=AtlasQuery(
                variant_id=self.variant.variant_id,
                include_encode_catalog=True,
            ),
        )
        observation = next(
            item for item in result.observations if item.feature_type == "assay_catalog"
        )
        self.assertEqual(observation.state, EvidenceState.ABSENT)

        with self.assertRaises(ValidationError):
            PublicAtlasRetriever(
                StubReferenceRetriever(),
                FixedEncodeClient({"@graph": []}, source_id="SRC-ENSEMBL-REST"),
            ).retrieve(
                self.variant,
                self.context,
                query=AtlasQuery(
                    variant_id=self.variant.variant_id,
                    include_encode_catalog=True,
                ),
            )

    def test_receipts_are_closed_over_observations(self) -> None:
        result = PublicAtlasRetriever(
            StubReferenceRetriever(),
            StubEncodeClient(),
        ).retrieve(
            self.variant,
            self.context,
            query=AtlasQuery(
                variant_id=self.variant.variant_id,
                include_encode_catalog=True,
            ),
        )
        retained = {receipt.request_hash: receipt for receipt in result.receipts}
        for observation in result.observations:
            if observation.receipt is not None:
                self.assertEqual(
                    retained.get(observation.receipt.request_hash),
                    observation.receipt,
                )

        receipt = _receipt("SRC-ENSEMBL-REST", "orphaned")
        observation = AtlasObservation(
            observation_id="orphaned-receipt",
            source_id=receipt.source_id,
            feature_type="reference_annotation",
            state=EvidenceState.SUPPORTED,
            tier=atlas_module.EvidenceTier.REFERENCE,
            summary="fixture observation",
            payload={},
            context_key=self.context.key,
            context_score=None,
            receipt=receipt,
        )
        with self.assertRaisesRegex(ValidationError, "not retained"):
            AtlasBundle.create(
                variant=self.variant,
                context=self.context,
                query=AtlasQuery(variant_id=self.variant.variant_id),
                source_bundle_address=content_hash({"fixture": True}),
                observations=(observation,),
                receipts=(),
                warnings=(),
            )

    def test_payloads_are_frozen_and_bundle_serialization_detects_mutation(self) -> None:
        raw = {"nested": {"value": 1}}
        observation = AtlasObservation(
            observation_id="immutable-observation",
            source_id="fixture-source",
            feature_type="fixture",
            state=EvidenceState.ABSTAINED,
            tier=atlas_module.EvidenceTier.REFERENCE,
            summary="fixture observation",
            payload=raw,
            context_key=self.context.key,
            context_score=None,
            receipt=None,
        )
        raw["nested"]["value"] = 2
        self.assertEqual(observation.payload["nested"]["value"], 1)
        with self.assertRaises(TypeError):
            observation.payload["nested"]["value"] = 3

        result = PublicAtlasRetriever(StubReferenceRetriever()).retrieve(
            self.variant,
            self.context,
        )
        object.__setattr__(result.observations[0], "summary", "post-construction mutation")
        with self.assertRaises(ValidationError):
            result.to_dict()

    def test_variant_and_context_addresses_bind_claim_conversion(self) -> None:
        result = PublicAtlasRetriever(StubReferenceRetriever()).retrieve(
            self.variant,
            self.context,
        )
        substituted_variant = parse_variant(
            "7:101:C>T",
            genome_build="GRCh38",
            variant_id=self.variant.variant_id,
        )
        with self.assertRaisesRegex(ValidationError, "variant scope"):
            result.to_evidence_claims(variant=substituted_variant, context=self.context)

        substituted_context = ReferenceContext(
            "GRCh38",
            "glioma",
            "adult",
            "stem_like",
            source_version="different",
        )
        with self.assertRaisesRegex(ValidationError, "context scope"):
            result.to_evidence_claims(variant=self.variant, context=substituted_context)

    def test_retrieval_and_claims_are_deterministic_without_invented_confidence(self) -> None:
        query = AtlasQuery(
            variant_id=self.variant.variant_id,
            window_bp=25,
            include_encode_catalog=True,
        )
        first = PublicAtlasRetriever(
            StubReferenceRetriever(),
            StubEncodeClient(),
        ).retrieve(self.variant, self.context, query=query)
        second = PublicAtlasRetriever(
            StubReferenceRetriever(),
            StubEncodeClient(),
        ).retrieve(self.variant, self.context, query=query)
        self.assertEqual(first.to_dict(), second.to_dict())
        first_claims = first.to_evidence_claims(variant=self.variant, context=self.context)
        second_claims = second.to_evidence_claims(variant=self.variant, context=self.context)
        self.assertEqual(
            tuple(item.to_dict() for item in first_claims),
            tuple(item.to_dict() for item in second_claims),
        )
        self.assertTrue(all(item.score is None for item in first_claims))
        self.assertTrue(all(item.confidence == 0.0 for item in first_claims))
        claim_ids = {item.evidence_id for item in first_claims}
        self.assertIsNotNone(first.uncertainty)
        self.assertTrue(
            all(
                evidence_id in claim_ids
                for component in first.uncertainty.components
                for evidence_id in component.evidence_ids
            )
        )

    def test_no_receipt_failure_uses_stable_noninvented_time(self) -> None:
        class FailedReference:
            def retrieve(self, variant, context, *, window_bp=None):
                raise SourceError("fixture offline")

        retriever = PublicAtlasRetriever(FailedReference())
        first = retriever.retrieve(self.variant, self.context)
        second = retriever.retrieve(self.variant, self.context)
        self.assertEqual(first.created_at, "1970-01-01T00:00:00+00:00")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertTrue(all(item.state is EvidenceState.ABSTAINED for item in first.observations))

    def test_reference_mismatch_is_an_abstention_not_support(self) -> None:
        sequence_receipt = _receipt("SRC-UCSC-REST", "mismatch")
        feature_receipt = _receipt("SRC-ENSEMBL-REST", "mismatch-features")
        sequence = SequenceSlice(
            assembly=self.context.genome_build,
            chromosome=self.variant.chromosome,
            start=self.variant.start,
            end=self.variant.start + 3,
            sequence="TCGT",
            source_id="SRC-UCSC-REST",
            receipt=sequence_receipt,
        )
        bundle = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context_key=self.context.key,
            sequence=sequence,
            elements=(),
            raw_features=(),
            receipts=(sequence_receipt, feature_receipt),
            warnings=(),
        )
        result = PublicAtlasRetriever(FixedReference(bundle)).retrieve(
            self.variant,
            self.context,
        )
        self.assertEqual(result.sequence_analysis.state, SequenceAnalysisState.REFERENCE_MISMATCH)
        observation = next(
            item for item in result.observations if item.feature_type == "motif_delta"
        )
        self.assertEqual(observation.state, EvidenceState.ABSTAINED)
        self.assertIsNone(observation.context_score)

    def test_truncated_track_report_abstains_instead_of_claiming_support(self) -> None:
        metadata = self._track_metadata("track-main", "SRC-TRACK-MAIN")
        rows = tuple(
            {
                "record_id": f"row-{index:03d}",
                "chromosome": self.variant.chromosome,
                "start": self.variant.start,
                "end": self.variant.end,
                "context_key": self.context.key,
                "payload": {"signal": index},
            }
            for index in range(101)
        )
        adapter = DeclaredReferenceTrackAdapter.from_rows(metadata, rows).adapter
        result = PublicAtlasRetriever(
            self._empty_reference(),
            track_adapters=ReferenceTrackAdapterRegistry((adapter,)),
        ).retrieve(self.variant, self.context)
        self.assertEqual(result.track_reports[0].state, ReferenceTrackQueryState.TRUNCATED)
        observation = next(
            item for item in result.observations if item.feature_type.startswith("reference_track:")
        )
        self.assertEqual(observation.state, EvidenceState.ABSTAINED)
        self.assertIsNone(observation.context_score)

    def test_configuration_and_track_registry_are_snapshotted(self) -> None:
        motif = MotifDefinition("motif-a", "motif A", "A")
        ranges = {"motif_delta_count": (0.0, 10.0)}
        profile = DomainProfile(
            profile_id="profile-a",
            context_key=self.context.key,
            required_features=("motif_delta_count",),
            feature_ranges=ranges,
            source_version="fixture-1",
        )
        adapter = DeclaredReferenceTrackAdapter.from_rows(
            self._track_metadata("track-one", "SRC-TRACK-ONE"),
            (
                {
                    "record_id": "one",
                    "chromosome": self.variant.chromosome,
                    "start": self.variant.start,
                    "end": self.variant.end,
                    "context_key": self.context.key,
                },
            ),
        ).adapter
        registry = ReferenceTrackAdapterRegistry((adapter,))
        retriever = PublicAtlasRetriever(
            self._empty_reference(),
            motifs=(motif,),
            domain_profile=profile,
            track_adapters=registry,
        )
        object.__setattr__(motif, "pattern", "T")
        ranges["motif_delta_count"] = (100.0, 200.0)
        registry.register(
            DeclaredReferenceTrackAdapter.from_rows(
                self._track_metadata("track-two", "SRC-TRACK-TWO"),
                (
                    {
                        "record_id": "two",
                        "chromosome": self.variant.chromosome,
                        "start": self.variant.start,
                        "end": self.variant.end,
                        "context_key": self.context.key,
                    },
                ),
            ).adapter
        )
        object.__setattr__(adapter.metadata, "display_name", "tampered after snapshot")

        self.assertEqual(retriever.motifs[0].pattern, "A")
        self.assertEqual(
            retriever.domain_profile.feature_ranges["motif_delta_count"],
            (0.0, 10.0),
        )
        self.assertEqual(len(retriever.track_adapters.list()), 1)
        result = retriever.retrieve(self.variant, self.context)
        self.assertEqual(len(result.track_reports), 1)
        self.assertEqual(result.track_reports[0].metadata.display_name, "track-one")

    def test_exported_limit_rebinding_cannot_expand_hard_ceiling(self) -> None:
        original = atlas_module.MAX_ATLAS_MOTIF_PATTERN_LENGTH
        atlas_module.MAX_ATLAS_MOTIF_PATTERN_LENGTH = 1_000_000
        try:
            oversized = MotifDefinition(
                "oversized",
                "oversized motif",
                "A" * (original + 1),
            )
            with self.assertRaisesRegex(ValidationError, "maximum length"):
                PublicAtlasRetriever(self._empty_reference(), motifs=(oversized,))
        finally:
            atlas_module.MAX_ATLAS_MOTIF_PATTERN_LENGTH = original

    def test_sequence_work_ceiling_abstains_before_dependency_execution(self) -> None:
        class CountingInference(SequenceInference):
            def __init__(self) -> None:
                super().__init__()
                self.calls = 0

            def analyze(self, variant, sequence, *, motifs=()):
                self.calls += 1
                return super().analyze(variant, sequence, motifs=motifs)

        sequence_receipt = _receipt("SRC-UCSC-REST", "large-sequence")
        feature_receipt = _receipt("SRC-ENSEMBL-REST", "large-features")
        sequence = SequenceSlice(
            assembly=self.context.genome_build,
            chromosome=self.variant.chromosome,
            start=self.variant.start,
            end=self.variant.start + 50_000,
            sequence="A" * 50_001,
            source_id="SRC-UCSC-REST",
            receipt=sequence_receipt,
        )
        bundle = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context_key=self.context.key,
            sequence=sequence,
            elements=(),
            raw_features=(),
            receipts=(sequence_receipt, feature_receipt),
            warnings=(),
        )
        inference = CountingInference()
        result = PublicAtlasRetriever(
            FixedReference(bundle),
            sequence_inference=inference,
            motifs=(MotifDefinition("motif-a", "motif A", "A"),),
        ).retrieve(
            self.variant,
            self.context,
            query=AtlasQuery(variant_id=self.variant.variant_id, window_bp=100_000),
        )
        self.assertEqual(inference.calls, 0)
        observation = next(
            item for item in result.observations if item.feature_type == "motif_delta"
        )
        self.assertEqual(observation.state, EvidenceState.ABSTAINED)
        self.assertIsNone(result.sequence_analysis)

    def _empty_reference(self):
        class EmptyReference:
            def retrieve(inner_self, variant, context, *, window_bp=None):
                return ReferenceBundle.create(
                    variant_id=variant.variant_id,
                    context_key=context.key,
                    sequence=None,
                    elements=(),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )

        return EmptyReference()

    def _track_metadata(self, adapter_id: str, source_id: str) -> ReferenceTrackMetadata:
        return ReferenceTrackMetadata(
            adapter_id=adapter_id,
            display_name=adapter_id,
            version="2026.09",
            assembly=self.context.genome_build,
            track_type="open_chromatin",
            source_id=source_id,
            source_version="fixture-1",
            license="CC-BY-4.0",
            access_mode=ReferenceAccessMode.LOCAL_CACHE,
            uri=f"urn:glio:track:{adapter_id}:2026.09",
            coordinate_system=CoordinateSystem.ONE_BASED_INCLUSIVE,
            supported_contexts=(self.context.key,),
            channels=("accessibility",),
            limitations=("Reference overlap is not evidence of causality.",),
        )


if __name__ == "__main__":
    unittest.main()
