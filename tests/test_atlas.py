from __future__ import annotations

import copy
import tempfile
import threading
import unittest
from typing import Any, cast
from unittest.mock import patch

import glio_noncode._callback_isolation as callback_isolation_module
import glio_noncode.atlas as atlas_module
import glio_noncode.data_sources as data_sources_module
import glio_noncode.sequence_inference as sequence_inference_module
from glio_noncode.atlas import (
    AtlasBundle,
    AtlasEncodeReplayState,
    AtlasObservation,
    AtlasQuery,
    AtlasReplayInputs,
    PublicAtlasRetriever,
)
from glio_noncode.data_sources import (
    EncodeRestClient,
    FetchReceipt,
    FetchStatus,
    PublicReferenceRetriever,
    ReferenceBundle,
    SequenceSlice,
    SourceClient,
    SourcePayload,
)
from glio_noncode.errors import SourceError, ValidationError
from glio_noncode.identity import parse_variant
from glio_noncode.models import (
    CandidateElement,
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
    VariantIdentity,
)
from glio_noncode.reference_manifest import ReferenceAccessMode
from glio_noncode.reference_registry import CoordinateSystem
from glio_noncode.reference_track_adapters import (
    DeclaredReferenceTrackAdapter,
    ReferenceTrackAdapterRegistry,
    ReferenceTrackMetadata,
    ReferenceTrackQueryReport,
    ReferenceTrackQueryState,
)
from glio_noncode.sequence_inference import (
    MotifDefinition,
    MotifHit,
    MotifScanner,
    SequenceAnalysisResult,
    SequenceAnalysisState,
    SequenceInference,
)
from glio_noncode.serialization import canonical_bytes, content_hash
from glio_noncode.uncertainty import DomainProfile, UncertaintyPropagator


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
            context=context,
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

    def test_public_atlas_can_reuse_an_exact_retained_reference_bundle(self) -> None:
        retained = StubReferenceRetriever().retrieve(
            self.variant,
            self.context,
            window_bp=2_000,
        )

        class ExplodingReference:
            def retrieve(self, variant, context, *, window_bp=None):
                raise AssertionError("retained reference bundle must prevent a refetch")

        result = PublicAtlasRetriever(ExplodingReference()).retrieve(
            self.variant,
            self.context,
            reference_bundle=retained,
        )

        self.assertEqual(result.source_bundle_address, retained.content_address)
        self.assertCountEqual(result.receipts, retained.receipts)

    def test_public_atlas_replays_uninterpreted_receipt_status_as_canonical_json(self) -> None:
        retained = self._retained_reference_bundle()
        extra_receipt = _receipt("SRC-UNINTERPRETED", "unused-source-payload")
        retained = ReferenceBundle.create(
            variant_id=retained.variant_id,
            context=self.context,
            sequence=retained.sequence,
            elements=retained.elements,
            raw_features=retained.raw_features,
            receipts=(*retained.receipts, extra_receipt),
            warnings=retained.warnings,
        )

        result = PublicAtlasRetriever(FixedReference(retained)).retrieve(
            self.variant,
            self.context,
        )
        observation = next(
            item
            for item in result.observations
            if item.source_id == extra_receipt.source_id
            and item.feature_type == "source_retrieval"
        )

        self.assertEqual(observation.payload["status"], FetchStatus.FETCHED.value)
        self.assertEqual(
            AtlasBundle.from_dict(
                result.to_dict(),
                self.variant,
                self.context,
                reference_bundle=retained,
                replay_inputs=result.replay_inputs,
            ).to_dict(),
            result.to_dict(),
        )

    def test_persisted_atlas_types_round_trip_every_nested_value(self) -> None:
        result = self._full_nested_atlas_bundle()
        raw = result.to_dict()

        self.assertEqual(AtlasQuery.from_dict(raw["query"]).to_dict(), raw["query"])
        self.assertEqual(
            AtlasObservation.from_dict(raw["observations"][0]).to_dict(),
            raw["observations"][0],
        )
        reopened = AtlasBundle.from_dict(
            raw,
            self.variant,
            self.context,
            reference_bundle=self._retained_reference_bundle(),
            replay_inputs=result.replay_inputs,
        )
        self.assertEqual(reopened.to_dict(), raw)
        self.assertIsNot(reopened, result)
        self.assertIsNot(reopened.query, result.query)
        self.assertIsNot(reopened.observations[0], result.observations[0])
        self.assertIsNot(reopened.sequence_analysis, result.sequence_analysis)
        self.assertIsNot(reopened.uncertainty, result.uncertainty)
        self.assertIsNot(reopened.track_reports[0], result.track_reports[0])

    def test_persisted_atlas_types_reject_non_utf8_text(self) -> None:
        source = self._full_nested_atlas_bundle()
        raw = source.to_dict()

        malformed_query = copy.deepcopy(raw["query"])
        malformed_query["encode_assay_title"] = "ATAC-\ud800"
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            AtlasQuery.from_dict(malformed_query)

        malformed_observation = copy.deepcopy(raw["observations"][0])
        malformed_observation["summary"] = "summary\ud800"
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            AtlasObservation.from_dict(malformed_observation)

        malformed_bundle = copy.deepcopy(raw)
        malformed_bundle["warnings"] = ["warning\ud800"]
        with self.assertRaises(ValidationError):
            AtlasBundle.from_dict(
                malformed_bundle,
                self.variant,
                self.context,
                reference_bundle=self._retained_reference_bundle(),
                replay_inputs=source.replay_inputs,
            )

    def test_persisted_atlas_bundle_rejects_malformed_nested_values(self) -> None:
        source = self._full_nested_atlas_bundle()
        baseline = source.to_dict()

        malformed_query = copy.deepcopy(baseline)
        malformed_query["query"]["unexpected"] = True

        malformed_receipt = copy.deepcopy(baseline)
        observation_with_receipt = next(
            item for item in malformed_receipt["observations"] if item["receipt"] is not None
        )
        observation_with_receipt["receipt"]["url"] = "file:///not-a-source"

        malformed_analysis = copy.deepcopy(baseline)
        malformed_analysis["sequence_analysis"]["created_hits"] = {}

        malformed_uncertainty = copy.deepcopy(baseline)
        malformed_uncertainty["uncertainty"]["components"][0]["evidence_ids"] = {}

        malformed_track_report = copy.deepcopy(baseline)
        malformed_track_report["track_reports"][0]["matches"] = {}

        for label, raw in (
            ("query", malformed_query),
            ("receipt", malformed_receipt),
            ("sequence_analysis", malformed_analysis),
            ("uncertainty", malformed_uncertainty),
            ("track_report", malformed_track_report),
        ):
            with self.subTest(label=label), self.assertRaises(ValidationError):
                AtlasBundle.from_dict(
                    raw,
                    self.variant,
                    self.context,
                    reference_bundle=self._retained_reference_bundle(),
                    replay_inputs=source.replay_inputs,
                )

    def test_persisted_atlas_bundle_rejects_coherently_readdressed_foreign_scope(self) -> None:
        source = self._full_nested_atlas_bundle()
        raw = source.to_dict()
        raw["variant_address"] = content_hash(
            {"foreign": True},
            prefix="atlas-variant",
        )
        # Uncertainty component evidence IDs intentionally bind the variant scope;
        # remove that optional projection so this regression reaches the direct
        # external variant-scope check with an otherwise coherent bundle address.
        raw["uncertainty"] = None
        raw["content_address"] = content_hash(
            {key: value for key, value in raw.items() if key != "content_address"}
        )

        with self.assertRaisesRegex(ValidationError, "variant scope"):
            AtlasBundle.from_dict(
                raw,
                self.variant,
                self.context,
                reference_bundle=self._retained_reference_bundle(),
                replay_inputs=source.replay_inputs,
            )

    def test_persisted_atlas_bundle_rejects_coherently_readdressed_window_shrink(self) -> None:
        source = self._full_nested_atlas_bundle()
        raw = source.to_dict()
        raw["query"]["window_bp"] = 1
        # The uncertainty projection binds the query independently. Remove that
        # optional projection so the regression reaches retained-window replay.
        raw["uncertainty"] = None
        raw["content_address"] = content_hash(
            {key: value for key, value in raw.items() if key != "content_address"}
        )

        with self.assertRaisesRegex(ValidationError, "escaped the requested atlas window"):
            AtlasBundle.from_dict(
                raw,
                self.variant,
                self.context,
                reference_bundle=self._retained_reference_bundle(),
                replay_inputs=source.replay_inputs,
            )

    def test_persisted_atlas_bundle_closes_arbitrary_and_reference_observations(self) -> None:
        source = self._full_nested_atlas_bundle()
        baseline = source.to_dict()

        arbitrary = copy.deepcopy(baseline)
        arbitrary_observation = AtlasObservation(
            observation_id=content_hash(
                {"source_id": "SRC-ARBITRARY", "payload": {"value": "forged"}},
                prefix="atlas-observation",
            ),
            source_id="SRC-ARBITRARY",
            feature_type="arbitrary_projection",
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.REFERENCE,
            summary="A syntactically valid but underived observation was injected.",
            payload={"value": "forged"},
            context_key=self.context.key,
            context_score=None,
            receipt=None,
            limitations=("This observation has no retained source preimage.",),
        ).to_dict()
        arbitrary["observations"].append(arbitrary_observation)
        arbitrary["observations"].sort(
            key=lambda item: (
                item["source_id"],
                item["feature_type"],
                item["observation_id"],
            )
        )
        arbitrary["content_address"] = content_hash(
            {key: value for key, value in arbitrary.items() if key != "content_address"}
        )

        forged_reference = copy.deepcopy(baseline)
        reference_observation = next(
            item
            for item in forged_reference["observations"]
            if item["feature_type"] == "reference_gene"
        )
        reference_observation["payload"]["feature"]["external_name"] = "FORGED_GENE"
        forged_feature_address = content_hash(
            reference_observation["payload"]["feature"],
            prefix="atlas-feature",
        )
        reference_observation["payload"]["feature_address"] = forged_feature_address
        reference_observation["observation_id"] = forged_feature_address
        forged_reference["observations"].sort(
            key=lambda item: (
                item["source_id"],
                item["feature_type"],
                item["observation_id"],
            )
        )
        # The optional uncertainty projection cites the original observation.
        # Removing it lets the forged feature and its coherent address reach the
        # retained-reference derivation comparison.
        forged_reference["uncertainty"] = None
        forged_reference["content_address"] = content_hash(
            {key: value for key, value in forged_reference.items() if key != "content_address"}
        )

        missing_reference = copy.deepcopy(baseline)
        missing_reference["observations"] = [
            item
            for item in missing_reference["observations"]
            if item["feature_type"] != "reference_gene"
        ]
        missing_reference["uncertainty"] = None
        missing_reference["content_address"] = content_hash(
            {key: value for key, value in missing_reference.items() if key != "content_address"}
        )

        for label, raw in (
            ("arbitrary", arbitrary),
            ("forged_reference", forged_reference),
            ("missing_reference", missing_reference),
        ):
            with self.subTest(label=label), self.assertRaisesRegex(
                ValidationError,
                "observations do not exactly reconstruct",
            ):
                AtlasBundle.from_dict(
                    raw,
                    self.variant,
                    self.context,
                    reference_bundle=self._retained_reference_bundle(),
                    replay_inputs=source.replay_inputs,
                )

    def test_persisted_atlas_bundle_closes_coherently_readdressed_receipts(self) -> None:
        source = self._full_nested_atlas_bundle()
        raw = source.to_dict()
        receipt = _receipt("SRC-ARBITRARY", "unclassified-receipt")
        raw["receipts"].append(receipt.to_dict())
        raw["receipts"].sort(key=lambda item: (item["source_id"], item["request_hash"]))
        raw["observations"].append(
            PublicAtlasRetriever._uninterpreted_receipt_observation(
                receipt,
                self.context,
                raw["source_bundle_address"],
            ).to_dict()
        )
        raw["observations"].sort(
            key=lambda item: (
                item["source_id"],
                item["feature_type"],
                item["observation_id"],
            )
        )
        raw["content_address"] = content_hash(
            {key: value for key, value in raw.items() if key != "content_address"}
        )

        with self.assertRaisesRegex(ValidationError, "receipts must equal"):
            AtlasBundle.from_dict(
                raw,
                self.variant,
                self.context,
                reference_bundle=self._retained_reference_bundle(),
                replay_inputs=source.replay_inputs,
            )

    def test_persisted_atlas_bundle_requires_every_exact_reference_receipt(self) -> None:
        reference_bundle = self._retained_reference_bundle()
        source = self._full_nested_atlas_bundle()
        baseline = source.to_dict()
        reference_receipt = next(
            item
            for item in reference_bundle.receipts
            if item.source_id == "SRC-ENSEMBL-REST"
        )

        removed = copy.deepcopy(baseline)
        removed["receipts"] = [
            item
            for item in removed["receipts"]
            if item["request_hash"] != reference_receipt.request_hash
        ]
        removed["observations"] = [
            item
            for item in removed["observations"]
            if item["receipt"] is None
            or item["receipt"]["request_hash"] != reference_receipt.request_hash
        ]
        removed["uncertainty"] = None
        removed["content_address"] = content_hash(
            {key: value for key, value in removed.items() if key != "content_address"}
        )

        substituted = copy.deepcopy(baseline)
        alternate_receipt = reference_receipt.to_dict()
        alternate_receipt["source_version"] = "fixture-substituted"
        substituted["receipts"] = [
            alternate_receipt
            if item["request_hash"] == reference_receipt.request_hash
            else item
            for item in substituted["receipts"]
        ]
        for observation in substituted["observations"]:
            receipt = observation["receipt"]
            if (
                receipt is not None
                and receipt["request_hash"] == reference_receipt.request_hash
            ):
                observation["receipt"] = copy.deepcopy(alternate_receipt)
        substituted["uncertainty"] = None
        substituted["content_address"] = content_hash(
            {key: value for key, value in substituted.items() if key != "content_address"}
        )

        for label, raw in (("removed", removed), ("substituted", substituted)):
            with self.subTest(label=label), self.assertRaisesRegex(
                ValidationError,
                "retain every exact reference receipt",
            ):
                AtlasBundle.from_dict(
                    raw,
                    self.variant,
                    self.context,
                    reference_bundle=reference_bundle,
                    replay_inputs=source.replay_inputs,
                )

    def test_persisted_atlas_bundle_closes_coherently_readdressed_warnings(self) -> None:
        source = self._full_nested_atlas_bundle()
        raw = source.to_dict()
        raw["warnings"].append("injected but canonically ordered atlas warning")
        raw["warnings"].sort()
        raw["content_address"] = content_hash(
            {key: value for key, value in raw.items() if key != "content_address"}
        )

        with self.assertRaisesRegex(ValidationError, "warnings must equal"):
            AtlasBundle.from_dict(
                raw,
                self.variant,
                self.context,
                reference_bundle=self._retained_reference_bundle(),
                replay_inputs=source.replay_inputs,
            )

    def test_persisted_atlas_bundle_requires_every_retained_reference_warning(self) -> None:
        reference_bundle = self._retained_reference_bundle()
        reference_warning = "retained reference fixture warning"
        reference_bundle = ReferenceBundle.create(
            variant_id=reference_bundle.variant_id,
            context=self.context,
            sequence=reference_bundle.sequence,
            elements=reference_bundle.elements,
            raw_features=reference_bundle.raw_features,
            receipts=reference_bundle.receipts,
            warnings=(reference_warning,),
        )
        source = PublicAtlasRetriever(FixedReference(reference_bundle)).retrieve(
            self.variant,
            self.context,
        )
        raw = source.to_dict()
        raw["warnings"].remove(reference_warning)
        raw["content_address"] = content_hash(
            {key: value for key, value in raw.items() if key != "content_address"}
        )

        with self.assertRaisesRegex(ValidationError, "retain every exact reference warning"):
            AtlasBundle.from_dict(
                raw,
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=source.replay_inputs,
            )

    def test_persisted_sequence_analysis_is_recomputed_from_retained_sequence(self) -> None:
        source = self._full_nested_atlas_bundle()
        baseline = source.to_dict()
        reference_bundle = self._retained_reference_bundle()
        cases = (
            ("reference_sequence_hash", content_hash("forged reference")),
            ("reference_interval", ["chr7", 101, 104]),
            ("reference_allele_observed", "C"),
            ("alternate_length_delta", 1),
            ("gc_fraction_reference", 0.25),
            ("gc_fraction_alternate", 0.25),
        )

        for field_name, forged_value in cases:
            raw = copy.deepcopy(baseline)
            analysis = raw["sequence_analysis"]
            analysis[field_name] = forged_value
            analysis["content_address"] = content_hash(
                {
                    "variant_id": analysis["variant_id"],
                    "source_id": analysis["source_id"],
                    "reference_interval": analysis["reference_interval"],
                    "reference_sequence_hash": analysis["reference_sequence_hash"],
                    "alternate_sequence_hash": analysis["alternate_sequence_hash"],
                    "created_hits": analysis["created_hits"],
                    "disrupted_hits": analysis["disrupted_hits"],
                    "alternate_length_delta": analysis["alternate_length_delta"],
                }
            )
            raw["content_address"] = content_hash(
                {key: value for key, value in raw.items() if key != "content_address"}
            )

            with self.subTest(field=field_name), self.assertRaises(ValidationError):
                AtlasBundle.from_dict(
                    raw,
                    self.variant,
                    self.context,
                    reference_bundle=reference_bundle,
                    replay_inputs=source.replay_inputs,
                )

    def test_persisted_sequence_analysis_binds_exact_reference_bundle(self) -> None:
        source = self._full_nested_atlas_bundle()
        raw = source.to_dict()
        sequence_receipt = _receipt("SRC-UCSC-REST", "foreign-sequence")
        foreign_sequence = SequenceSlice(
            assembly=self.context.genome_build,
            chromosome=self.variant.chromosome,
            start=self.variant.start,
            end=self.variant.start + 3,
            sequence="AGGT",
            source_id="SRC-UCSC-REST",
            receipt=sequence_receipt,
        )
        foreign_bundle = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context=self.context,
            sequence=foreign_sequence,
            elements=(),
            raw_features=(),
            receipts=(sequence_receipt,),
            warnings=(),
        )
        raw["source_bundle_address"] = foreign_bundle.content_address
        raw["uncertainty"] = None
        raw["content_address"] = content_hash(
            {key: value for key, value in raw.items() if key != "content_address"}
        )

        with self.assertRaisesRegex(ValidationError, "replay inputs content_address"):
            AtlasBundle.from_dict(
                raw,
                self.variant,
                self.context,
                reference_bundle=foreign_bundle,
                replay_inputs=source.replay_inputs,
            )

    def test_persisted_ood_address_is_versioned_and_recomputed(self) -> None:
        reference_bundle = self._retained_reference_bundle()
        profile = DomainProfile(
            profile_id="profile-replay-v1",
            context_key=self.context.key,
            required_features=("motif_delta_count",),
            feature_ranges={"motif_delta_count": (0.0, 10.0)},
            source_version="fixture-1",
        )
        result = PublicAtlasRetriever(
            FixedReference(reference_bundle),
            domain_profile=profile,
        ).retrieve(self.variant, self.context)
        baseline = result.to_dict()
        ood = baseline["uncertainty"]["ood"]
        self.assertTrue(ood["content_address"].startswith("atlas-ood-v1:"))
        self.assertEqual(
            AtlasBundle.from_dict(
                baseline,
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=result.replay_inputs,
            ).to_dict(),
            baseline,
        )

        for forged_address in (
            "sha256:" + "0" * 64,
            "atlas-ood-v1:" + "0" * 64,
        ):
            raw = copy.deepcopy(baseline)
            uncertainty = raw["uncertainty"]
            uncertainty["ood"]["content_address"] = forged_address
            uncertainty["content_address"] = content_hash(
                {
                    "overall": uncertainty["overall"],
                    "band": uncertainty["band"],
                    "components": uncertainty["components"],
                    "ood": uncertainty["ood"],
                }
            )
            raw["content_address"] = content_hash(
                {key: value for key, value in raw.items() if key != "content_address"}
            )

            with self.subTest(address=forged_address), self.assertRaisesRegex(
                ValidationError,
                "OOD content_address does not match its retained fields",
            ):
                AtlasBundle.from_dict(
                    raw,
                    self.variant,
                    self.context,
                    reference_bundle=reference_bundle,
                    replay_inputs=result.replay_inputs,
                )

    def test_replay_inputs_are_external_content_addressed_and_exactly_round_trip(self) -> None:
        reference_bundle = self._retained_reference_bundle()
        result = self._full_nested_atlas_bundle()
        raw_inputs = result.replay_inputs.to_dict()

        reopened = AtlasReplayInputs.from_dict(
            raw_inputs,
            self.variant,
            self.context,
            reference_bundle=reference_bundle,
        )

        self.assertEqual(reopened.to_dict(), raw_inputs)
        self.assertEqual(result.replay_inputs_address, reopened.content_address)
        self.assertEqual(result.to_dict()["replay_inputs_address"], reopened.content_address)
        self.assertNotIn("replay_inputs", result.to_dict())
        self.assertEqual(len(reopened.track_adapters), 1)

    def test_persisted_atlas_requires_the_exact_external_replay_inputs(self) -> None:
        reference_bundle = self._retained_reference_bundle()
        result = self._full_nested_atlas_bundle()
        substitute = PublicAtlasRetriever(
            FixedReference(reference_bundle),
            motifs=(MotifDefinition("substitute", "substitute", "T"),),
        ).retrieve(self.variant, self.context)

        with self.assertRaisesRegex(ValidationError, "AtlasReplayInputs"):
            AtlasBundle.from_dict(
                result.to_dict(),
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=None,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "exact replay inputs"):
            AtlasBundle.from_dict(
                result.to_dict(),
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=substitute.replay_inputs,
            )

    def test_replay_rejects_coherent_uncertainty_removal_and_created_at_rewrite(self) -> None:
        result = self._full_nested_atlas_bundle()
        reference_bundle = self._retained_reference_bundle()

        removed_uncertainty = result.to_dict()
        removed_uncertainty["uncertainty"] = None
        removed_uncertainty["content_address"] = content_hash(
            {
                key: value
                for key, value in removed_uncertainty.items()
                if key != "content_address"
            }
        )
        with self.assertRaisesRegex(ValidationError, "uncertainty does not replay"):
            AtlasBundle.from_dict(
                removed_uncertainty,
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=result.replay_inputs,
            )

        rewritten_time = result.to_dict()
        rewritten_time["created_at"] = "2030-01-01T00:00:00+00:00"
        rewritten_time["content_address"] = content_hash(
            {key: value for key, value in rewritten_time.items() if key != "content_address"}
        )
        with self.assertRaisesRegex(ValidationError, "receipt-derived timestamp"):
            AtlasBundle.from_dict(
                rewritten_time,
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=result.replay_inputs,
            )

    def test_replay_rejects_a_coherent_valid_but_unconfigured_motif_hit(self) -> None:
        result = self._full_nested_atlas_bundle()
        reference_bundle = self._retained_reference_bundle()
        analysis = result.sequence_analysis
        sequence = reference_bundle.sequence
        self.assertIsNotNone(analysis)
        self.assertIsNotNone(sequence)
        assert analysis is not None and sequence is not None
        forged_hit = MotifHit(
            motif_id="forged-t",
            name="forged valid alternate T",
            start=self.variant.start,
            end=self.variant.start,
            strand="+",
            matched_sequence="T",
            source_id="forged-motif-source",
        )
        analysis_payload = {
            "variant_id": analysis.variant_id,
            "source_id": analysis.source_id,
            "reference_interval": analysis.reference_interval,
            "reference_sequence_hash": analysis.reference_sequence_hash,
            "alternate_sequence_hash": analysis.alternate_sequence_hash,
            "created_hits": (forged_hit,),
            "disrupted_hits": analysis.disrupted_hits,
            "alternate_length_delta": analysis.alternate_length_delta,
        }
        forged_analysis = SequenceAnalysisResult(
            variant_id=analysis.variant_id,
            state=analysis.state,
            source_id=analysis.source_id,
            reference_interval=analysis.reference_interval,
            reference_sequence_hash=analysis.reference_sequence_hash,
            alternate_sequence_hash=analysis.alternate_sequence_hash,
            reference_allele_observed=analysis.reference_allele_observed,
            alternate_length_delta=analysis.alternate_length_delta,
            gc_fraction_reference=analysis.gc_fraction_reference,
            gc_fraction_alternate=analysis.gc_fraction_alternate,
            created_hits=(forged_hit,),
            disrupted_hits=analysis.disrupted_hits,
            limitations=analysis.limitations,
            content_address=content_hash(analysis_payload),
        )
        forged_observation = PublicAtlasRetriever._sequence_analysis_observation(
            forged_analysis,
            self.context,
            sequence.receipt,
        )
        observations = tuple(
            forged_observation if item.feature_type == "motif_delta" else item
            for item in result.observations
        )
        forged = self._coherently_rebuild(
            result,
            observations=observations,
            sequence_analysis=forged_analysis,
            track_reports=result.track_reports,
        )

        with self.assertRaisesRegex(ValidationError, "sequence analysis does not replay"):
            AtlasBundle.from_dict(
                forged.to_dict(),
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=result.replay_inputs,
            )

    def test_replay_rejects_coherent_track_report_and_observation_removal(self) -> None:
        result = self._full_nested_atlas_bundle()
        forged = self._coherently_rebuild(
            result,
            observations=tuple(
                item
                for item in result.observations
                if not item.feature_type.startswith("reference_track:")
            ),
            sequence_analysis=result.sequence_analysis,
            track_reports=(),
        )

        with self.assertRaisesRegex(ValidationError, "track reports do not replay"):
            AtlasBundle.from_dict(
                forged.to_dict(),
                self.variant,
                self.context,
                reference_bundle=self._retained_reference_bundle(),
                replay_inputs=result.replay_inputs,
            )

    def test_replay_rejects_coherent_encode_accession_substitution(self) -> None:
        reference_bundle = self._retained_reference_bundle()
        query = AtlasQuery(
            variant_id=self.variant.variant_id,
            include_encode_catalog=True,
        )
        result = PublicAtlasRetriever(
            FixedReference(reference_bundle),
            StubEncodeClient(),
        ).retrieve(self.variant, self.context, query=query)
        original = next(
            item for item in result.observations if item.feature_type == "assay_catalog"
        )
        receipt = original.receipt
        self.assertIsNotNone(receipt)
        assert receipt is not None
        substituted_accessions = ["ENCSR999ZZZ"]
        substituted = AtlasObservation(
            observation_id=content_hash(
                {
                    "request_hash": receipt.request_hash,
                    "response_hash": receipt.response_hash,
                    "record_count": 1,
                    "accessions": substituted_accessions,
                },
                prefix="atlas-observation",
            ),
            source_id=original.source_id,
            feature_type=original.feature_type,
            state=original.state,
            tier=original.tier,
            summary=original.summary,
            payload={
                "record_count": 1,
                "accessions": substituted_accessions,
                "request_hash": receipt.request_hash,
                "response_hash": receipt.response_hash,
            },
            context_key=original.context_key,
            context_score=original.context_score,
            receipt=receipt,
            limitations=original.limitations,
        )
        forged = self._coherently_rebuild(
            result,
            observations=tuple(
                substituted if item.feature_type == "assay_catalog" else item
                for item in result.observations
            ),
            sequence_analysis=result.sequence_analysis,
            track_reports=result.track_reports,
        )

        with self.assertRaisesRegex(ValidationError, "observations do not exactly reconstruct"):
            AtlasBundle.from_dict(
                forged.to_dict(),
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=result.replay_inputs,
            )

    def test_injected_derivers_must_match_builtin_offline_replay(self) -> None:
        class DivergentSequenceInference:
            def analyze(inner_self, variant, sequence, *, motifs=()):
                return SequenceInference().analyze(
                    variant,
                    sequence,
                    motifs=(MotifDefinition("injected-t", "injected T", "T"),),
                )

        class DivergentUncertaintyPropagator:
            def summarize(inner_self, claims, *, ood=None):
                return UncertaintyPropagator().summarize((), ood=ood)

        for label, kwargs, message in (
            (
                "sequence",
                {"sequence_inference": DivergentSequenceInference()},
                "sequence analysis does not replay",
            ),
            (
                "uncertainty",
                {"uncertainty_propagator": DivergentUncertaintyPropagator()},
                "uncertainty does not replay",
            ),
        ):
            with self.subTest(label=label), self.assertRaisesRegex(ValidationError, message):
                PublicAtlasRetriever(
                    FixedReference(self._retained_reference_bundle()),
                    **kwargs,
                ).retrieve(self.variant, self.context)

    def test_encode_source_failure_replays_with_its_exact_receipt_state(self) -> None:
        fetched_failure_receipt = _receipt("SRC-ENCODE-REST", "failure-with-content-receipt")

        class FailedEncode:
            def search_experiments(inner_self, **kwargs):
                raise SourceError("fixture catalog failure", receipt=fetched_failure_receipt)

        reference_bundle = self._retained_reference_bundle()
        result = PublicAtlasRetriever(
            FixedReference(reference_bundle),
            FailedEncode(),
        ).retrieve(
            self.variant,
            self.context,
            query=AtlasQuery(
                variant_id=self.variant.variant_id,
                include_encode_catalog=True,
            ),
        )

        self.assertEqual(result.replay_inputs.encode_state, AtlasEncodeReplayState.FAILURE)
        self.assertEqual(result.replay_inputs.encode_failure_receipt, fetched_failure_receipt)
        self.assertEqual(
            AtlasBundle.from_dict(
                result.to_dict(),
                self.variant,
                self.context,
                reference_bundle=reference_bundle,
                replay_inputs=result.replay_inputs,
            ).to_dict(),
            result.to_dict(),
        )

    def test_no_feature_overlap_is_absent_not_a_disease_negative(self) -> None:
        reference = StubReferenceRetriever()
        bundle = reference.retrieve(self.variant, self.context, window_bp=10)
        empty_bundle = ReferenceBundle.create(
            variant_id=bundle.variant_id,
            context=self.context,
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
            context=self.context,
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
            context=self.context,
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

    def test_candidate_materialization_failure_retains_raw_audit_input_and_abstains(self) -> None:
        original = StubReferenceRetriever().retrieve(self.variant, self.context, window_bp=10)
        malformed_feature = {
            "feature_type": "regulatory",
            "id": "malformed-coordinate-feature",
            "seq_region_name": "7",
            "start": self.variant.start + 5,
            "end": self.variant.start,
        }
        retained = ReferenceBundle.create(
            variant_id=original.variant_id,
            context=self.context,
            sequence=original.sequence,
            elements=(),
            raw_features=(malformed_feature,),
            receipts=original.receipts,
            warnings=(
                "candidate materialization abstained: reference regulatory feature has "
                "invalid coordinates",
            ),
        )

        result = PublicAtlasRetriever(FixedReference(retained)).retrieve(
            self.variant,
            self.context,
        )
        annotation = next(
            item
            for item in result.observations
            if item.payload.get("feature_address")
            == content_hash(malformed_feature, prefix="atlas-feature")
        )
        self.assertEqual(annotation.state, EvidenceState.ABSTAINED)
        self.assertEqual(annotation.payload["feature"], malformed_feature)
        self.assertIn("audit only", annotation.limitations[0])
        claim = next(
            item
            for item in result.to_evidence_claims(
                variant=self.variant,
                context=self.context,
            )
            if item.channel == annotation.feature_type
        )
        self.assertEqual(claim.state, EvidenceState.ABSTAINED)
        self.assertEqual(
            AtlasBundle.from_dict(
                result.to_dict(),
                self.variant,
                self.context,
                reference_bundle=retained,
                replay_inputs=result.replay_inputs,
            ).to_dict(),
            result.to_dict(),
        )

        unclassified_feature = {"garbage": True}
        unclassified = ReferenceBundle.create(
            variant_id=original.variant_id,
            context=self.context,
            sequence=original.sequence,
            elements=(),
            raw_features=(unclassified_feature,),
            receipts=original.receipts,
            warnings=(),
        )
        unclassified_result = PublicAtlasRetriever(FixedReference(unclassified)).retrieve(
            self.variant,
            self.context,
        )
        unclassified_observation = next(
            item
            for item in unclassified_result.observations
            if item.payload.get("feature_address")
            == content_hash(unclassified_feature, prefix="atlas-feature")
        )
        self.assertEqual(unclassified_observation.state, EvidenceState.ABSTAINED)
        self.assertIn("materialization abstained", unclassified_observation.limitations[0])

        retrieval_failure = ReferenceBundle.create(
            variant_id=original.variant_id,
            context=self.context,
            sequence=original.sequence,
            elements=(),
            raw_features=(original.raw_features[0],),
            receipts=original.receipts,
            warnings=("feature retrieval abstained: malformed Ensembl response",),
        )
        with self.assertRaisesRegex(
            ValidationError,
            "retains features after a failed feature retrieval",
        ):
            PublicAtlasRetriever(FixedReference(retrieval_failure)).retrieve(
                self.variant,
                self.context,
            )

    def test_oversized_reference_feature_compacts_to_replayable_abstention(self) -> None:
        original = self._retained_reference_bundle()
        feature = {
            "feature_type": "regulatory",
            "id": "oversized-reference-feature",
            "description": "x" * (atlas_module.MAX_ATLAS_OBSERVATION_PAYLOAD_BYTES + 1),
        }
        retained = ReferenceBundle.create(
            variant_id=original.variant_id,
            context=self.context,
            sequence=original.sequence,
            elements=(),
            raw_features=(feature,),
            receipts=original.receipts,
            warnings=(),
        )

        result = PublicAtlasRetriever(FixedReference(retained)).retrieve(
            self.variant,
            self.context,
        )
        observation = next(
            item
            for item in result.observations
            if item.payload.get("feature_address")
            == content_hash(feature, prefix="atlas-feature")
        )
        self.assertEqual(observation.state, EvidenceState.ABSTAINED)
        self.assertEqual(
            observation.payload["projection"],
            "omitted_over_atlas_observation_payload_ceiling",
        )
        self.assertNotIn("feature", observation.payload)
        self.assertEqual(
            observation.payload["feature_canonical_bytes"],
            len(canonical_bytes(feature)),
        )
        self.assertEqual(
            observation.payload["source_bundle_address"],
            retained.content_address,
        )

        reopened = AtlasBundle.from_dict(
            result.to_dict(),
            self.variant,
            self.context,
            reference_bundle=retained,
            replay_inputs=result.replay_inputs,
        )
        self.assertEqual(reopened.to_dict(), result.to_dict())
        claim = next(
            item
            for item in reopened.to_evidence_claims(
                variant=self.variant,
                context=self.context,
            )
            if item.payload["observation"]["observation_id"]
            == observation.observation_id
        )
        self.assertEqual(claim.state, EvidenceState.ABSTAINED)

    def test_observation_projection_has_an_exact_byte_boundary(self) -> None:
        ceiling = atlas_module.MAX_ATLAS_OBSERVATION_PAYLOAD_BYTES
        empty_size = len(canonical_bytes({"blob": ""}))
        at_boundary = {"blob": "x" * (ceiling - empty_size)}
        over_boundary = {"blob": "x" * (ceiling - empty_size + 1)}
        self.assertEqual(len(canonical_bytes(at_boundary)), ceiling)
        self.assertEqual(len(canonical_bytes(over_boundary)), ceiling + 1)

        retained, retained_was_compacted = atlas_module._project_observation_payload(
            at_boundary,
            {"artifact_address": content_hash("boundary")},
            artifact_kind="boundary_fixture",
        )
        compact, compacted = atlas_module._project_observation_payload(
            over_boundary,
            {"artifact_address": content_hash("over-boundary")},
            artifact_kind="boundary_fixture",
        )
        self.assertIs(retained, at_boundary)
        self.assertFalse(retained_was_compacted)
        self.assertTrue(compacted)
        self.assertEqual(compact["expanded_payload_canonical_bytes"], ceiling + 1)
        self.assertNotIn("blob", compact)

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
            context=self.context,
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
            context=self.context,
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
            context=self.context,
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
            context=self.context,
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
                self.assertEqual(
                    result.replay_inputs.encode_state,
                    AtlasEncodeReplayState.PAYLOAD,
                )
                self.assertEqual(
                    AtlasBundle.from_dict(
                        result.to_dict(),
                        self.variant,
                        self.context,
                        reference_bundle=self._retained_reference_bundle(),
                        replay_inputs=result.replay_inputs,
                    ).to_dict(),
                    result.to_dict(),
                )

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
        reference_bundle = self._retained_reference_bundle()
        query = AtlasQuery(variant_id=self.variant.variant_id)
        replay_inputs = AtlasReplayInputs.create(
            variant=self.variant,
            context=self.context,
            query=query,
            reference_bundle=reference_bundle,
        )
        with self.assertRaisesRegex(ValidationError, "not retained"):
            AtlasBundle.create(
                variant=self.variant,
                context=self.context,
                query=query,
                source_bundle_address=reference_bundle.content_address,
                replay_inputs=replay_inputs,
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

    def test_full_variant_identity_binds_replay_rehydration_and_claims(self) -> None:
        reference_bundle = self._retained_reference_bundle()
        result = self._full_nested_atlas_bundle()
        substitutions = {
            "origin": "somatic",
            "clonality": "clonal",
            "sample_id": "sample-substituted",
            "annotations": {"cohort": "substituted"},
        }

        for field_name, substituted_value in substitutions.items():
            raw_variant = self.variant.to_dict()
            raw_variant[field_name] = substituted_value
            substituted_variant = VariantIdentity.from_dict(raw_variant)
            with self.subTest(field=field_name, surface="replay_inputs"), self.assertRaises(
                ValidationError
            ):
                AtlasReplayInputs.from_dict(
                    result.replay_inputs.to_dict(),
                    substituted_variant,
                    self.context,
                    reference_bundle=reference_bundle,
                )
            with self.subTest(field=field_name, surface="atlas_bundle"), self.assertRaises(
                ValidationError
            ):
                AtlasBundle.from_dict(
                    result.to_dict(),
                    substituted_variant,
                    self.context,
                    reference_bundle=reference_bundle,
                    replay_inputs=result.replay_inputs,
                )
            with self.subTest(field=field_name, surface="claims"), self.assertRaisesRegex(
                ValidationError,
                "variant scope",
            ):
                result.to_evidence_claims(
                    variant=substituted_variant,
                    context=self.context,
                )

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
        uncertainty = first.uncertainty
        self.assertIsNotNone(uncertainty)
        assert uncertainty is not None
        self.assertTrue(
            all(
                evidence_id in claim_ids
                for component in uncertainty.components
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
            context=self.context,
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
        sequence_analysis = result.sequence_analysis
        self.assertIsNotNone(sequence_analysis)
        assert sequence_analysis is not None
        self.assertEqual(sequence_analysis.state, SequenceAnalysisState.REFERENCE_MISMATCH)
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
        domain_profile = retriever.domain_profile
        self.assertIsNotNone(domain_profile)
        assert domain_profile is not None
        self.assertEqual(
            domain_profile.feature_ranges["motif_delta_count"],
            (0.0, 10.0),
        )
        track_adapters = retriever.track_adapters
        self.assertIsNotNone(track_adapters)
        assert track_adapters is not None
        self.assertEqual(len(track_adapters.list()), 1)
        result = retriever.retrieve(self.variant, self.context)
        self.assertEqual(len(result.track_reports), 1)
        self.assertEqual(result.track_reports[0].metadata.display_name, "track-one")

    def test_callback_cannot_redirect_the_canonical_variant_scope(self) -> None:
        original_start = self.variant.start

        class MutatingReference:
            def retrieve(self, variant, context, *, window_bp):
                object.__setattr__(variant, "start", variant.start + 1)
                object.__setattr__(variant, "end", variant.end + 1)
                return StubReferenceRetriever().retrieve(
                    variant,
                    context,
                    window_bp=window_bp,
                )

        with self.assertRaisesRegex(ValidationError, "mutated invocation scope"):
            PublicAtlasRetriever(MutatingReference()).retrieve(
                self.variant,
                self.context,
            )
        self.assertEqual(self.variant.start, original_start)

    def test_callback_cannot_rewrite_atlas_semantics_and_poison_a_later_call(self) -> None:
        def replacement_scope_factory():
            retained_scope_state = object()

            def replacement_scope():
                _ = retained_scope_state
                yield

            return replacement_scope

        original_supported_types = atlas_module._SUPPORTED_REFERENCE_FEATURE_TYPES
        original_feature_source = PublicAtlasRetriever._FEATURE_SOURCE
        retained = self._retained_reference_bundle()
        atlas_scope = cast(Any, atlas_module.atlas_callback_scope)
        atlas_scope_dict = atlas_scope.__dict__
        atlas_scope_dict_items = tuple(atlas_scope_dict.items())
        atlas_scope_wrapped = atlas_scope.__wrapped__
        atlas_scope_wrapped_code = atlas_scope_wrapped.__code__
        isolation_error_type = callback_isolation_module.ValidationError
        replacement_scope = replacement_scope_factory()

        def restore_callback_scope() -> None:
            atlas_scope.__dict__ = atlas_scope_dict
            atlas_scope_dict.clear()
            atlas_scope_dict.update(dict(atlas_scope_dict_items))
            atlas_scope_wrapped.__code__ = atlas_scope_wrapped_code
            vars(callback_isolation_module)["ValidationError"] = isolation_error_type

        self.addCleanup(restore_callback_scope)

        class MutatingReference:
            def retrieve(inner_self, variant, context, *, window_bp):
                atlas_module._SUPPORTED_REFERENCE_FEATURE_TYPES = frozenset({"garbage"})
                PublicAtlasRetriever._FEATURE_SOURCE = "SRC-POISONED"
                atlas_scope.__dict__ = {"__wrapped__": replacement_scope}
                atlas_scope_wrapped.__code__ = replacement_scope.__code__
                vars(callback_isolation_module)["ValidationError"] = RuntimeError
                return retained

        with self.assertRaisesRegex(ValidationError, "package semantic state"):
            PublicAtlasRetriever(MutatingReference()).retrieve(
                self.variant,
                self.context,
            )
        self.assertIs(
            atlas_module._SUPPORTED_REFERENCE_FEATURE_TYPES,
            original_supported_types,
        )
        self.assertIs(PublicAtlasRetriever._FEATURE_SOURCE, original_feature_source)
        self.assertIs(atlas_scope.__dict__, atlas_scope_dict)
        self.assertIs(atlas_scope.__wrapped__, atlas_scope_wrapped)
        self.assertIs(atlas_scope_wrapped.__code__, atlas_scope_wrapped_code)
        self.assertIs(callback_isolation_module.ValidationError, isolation_error_type)

        clean = PublicAtlasRetriever(FixedReference(retained)).retrieve(
            self.variant,
            self.context,
        )
        gene = next(
            item for item in clean.observations if item.feature_type == "reference_gene"
        )
        self.assertEqual(gene.state, EvidenceState.SUPPORTED)
        self.assertTrue(
            all(item.feature_type != "reference_garbage" for item in clean.observations)
        )

    def test_callback_cannot_mutate_sequence_semantic_mapping_in_place(self) -> None:
        iupac = sequence_inference_module._IUPAC
        original = dict(iupac)
        retained = self._retained_reference_bundle()

        class MutatingReference:
            def retrieve(inner_self, variant, context, *, window_bp):
                iupac["A"] = frozenset({"C"})
                return retained

        with self.assertRaisesRegex(ValidationError, "package semantic state"):
            PublicAtlasRetriever(MutatingReference()).retrieve(
                self.variant,
                self.context,
            )
        self.assertIs(sequence_inference_module._IUPAC, iupac)
        self.assertEqual(iupac, original)

    def test_callback_cannot_shadow_atlas_restore_builtins(self) -> None:
        retained = self._retained_reference_bundle()
        namespace = vars(atlas_module)
        missing = object()
        poisoned_names = (
            "dict",
            "Exception",
            "BaseException",
            "globals",
            "type",
            "vars",
            "cast",
            "detached_callback_guard",
            "_restore_atlas_object_configuration",
        )

        for poisoned_name in poisoned_names:
            with self.subTest(poisoned_name=poisoned_name):
                original = namespace.get(poisoned_name, missing)

                class ShadowingReference:
                    def __init__(inner_self, selected_name: str) -> None:
                        inner_self.selected_name = selected_name

                    def retrieve(inner_self, variant, context, *, window_bp):
                        del variant, context, window_bp
                        namespace[inner_self.selected_name] = None
                        return retained

                try:
                    with self.assertRaisesRegex(ValidationError, "package semantic state"):
                        PublicAtlasRetriever(ShadowingReference(poisoned_name)).retrieve(
                            self.variant,
                            self.context,
                        )
                    if original is missing:
                        self.assertNotIn(poisoned_name, namespace)
                    else:
                        self.assertIs(namespace[poisoned_name], original)

                    clean = PublicAtlasRetriever(FixedReference(retained)).retrieve(
                        self.variant,
                        self.context,
                    )
                    self.assertEqual(clean.variant_id, self.variant.variant_id)
                finally:
                    if original is missing:
                        namespace.pop(poisoned_name, None)
                    else:
                        namespace[poisoned_name] = original

    def test_callback_cannot_mutate_transitive_source_class_mapping(self) -> None:
        assemblies = data_sources_module.UcscRestClient._assemblies
        original = dict(assemblies)
        retained = self._retained_reference_bundle()

        class MutatingReference:
            def retrieve(inner_self, variant, context, *, window_bp):
                assemblies["GRCh38"] = "poisoned-build"
                return retained

        with self.assertRaisesRegex(ValidationError, "package semantic state"):
            PublicAtlasRetriever(MutatingReference()).retrieve(
                self.variant,
                self.context,
            )
        self.assertIs(data_sources_module.UcscRestClient._assemblies, assemblies)
        self.assertEqual(assemblies, original)

    def test_callback_cannot_shadow_retrieve_or_swap_atlas_instance_type(self) -> None:
        retained = self._retained_reference_bundle()
        holder: list[PublicAtlasRetriever] = []

        class PoisonedAtlas(PublicAtlasRetriever):
            pass

        class MutatingReference:
            def __init__(inner_self) -> None:
                inner_self.mutated = False

            def retrieve(inner_self, variant, context, *, window_bp):
                if not inner_self.mutated:
                    inner_self.mutated = True
                    target = holder[0]
                    target.retrieve = lambda *_args, **_kwargs: retained  # type: ignore[method-assign]
                    target.__class__ = PoisonedAtlas
                return retained

        retriever = PublicAtlasRetriever(MutatingReference())
        holder.append(retriever)
        with self.assertRaisesRegex(ValidationError, "retriever configuration"):
            retriever.retrieve(self.variant, self.context)

        self.assertIs(type(retriever), PublicAtlasRetriever)
        self.assertNotIn("retrieve", vars(retriever))
        clean = retriever.retrieve(self.variant, self.context)
        self.assertEqual(clean.variant_id, self.variant.variant_id)

    def test_callback_class_setattr_poison_is_restored_before_instance_state(self) -> None:
        retained = self._retained_reference_bundle()

        class MutatingReference:
            def __init__(inner_self) -> None:
                inner_self.mutated = False

            def retrieve(inner_self, variant, context, *, window_bp):
                if not inner_self.mutated:
                    inner_self.mutated = True

                    def reject_setattr(_target, _name, _value):
                        raise RuntimeError("poisoned atlas setattr")

                    type.__setattr__(PublicAtlasRetriever, "__setattr__", reject_setattr)
                return retained

        retriever = PublicAtlasRetriever(MutatingReference())
        try:
            with self.assertRaisesRegex(ValidationError, "package semantic state"):
                retriever.retrieve(self.variant, self.context)
            self.assertNotIn("__setattr__", vars(PublicAtlasRetriever))
            self.assertEqual(
                retriever.retrieve(self.variant, self.context).variant_id,
                self.variant.variant_id,
            )
        finally:
            if "__setattr__" in vars(PublicAtlasRetriever):
                type.__delattr__(PublicAtlasRetriever, "__setattr__")

    def test_callback_cannot_replace_builtin_scanner_or_uncertainty_binding(self) -> None:
        retained = self._retained_reference_bundle()
        inference = SequenceInference()
        uncertainty = UncertaintyPropagator()
        original_scanner = inference.scanner

        class MutatingReference:
            def __init__(inner_self) -> None:
                inner_self.calls = 0

            def retrieve(inner_self, variant, context, *, window_bp):
                inner_self.calls += 1
                if inner_self.calls == 1:
                    inference.scanner = MotifScanner()
                elif inner_self.calls == 2:
                    uncertainty.summarize = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
                return retained

        retriever = PublicAtlasRetriever(
            MutatingReference(),
            sequence_inference=inference,
            uncertainty_propagator=uncertainty,
        )
        with self.assertRaisesRegex(ValidationError, "retriever configuration"):
            retriever.retrieve(self.variant, self.context)
        self.assertIs(inference.scanner, original_scanner)

        with self.assertRaisesRegex(ValidationError, "retriever configuration"):
            retriever.retrieve(self.variant, self.context)
        self.assertNotIn("summarize", vars(uncertainty))

        clean = retriever.retrieve(self.variant, self.context)
        self.assertIsNotNone(clean.uncertainty)

    def test_callback_cannot_replace_custom_dependency_class_callable(self) -> None:
        retained = self._retained_reference_bundle()

        class DelegatingUncertainty:
            def summarize(inner_self, claims, *, ood=None):
                return UncertaintyPropagator().summarize(claims, ood=ood)

        original_summarize = vars(DelegatingUncertainty)["summarize"]

        class MutatingReference:
            def __init__(inner_self) -> None:
                inner_self.mutated = False

            def retrieve(inner_self, variant, context, *, window_bp):
                if not inner_self.mutated:
                    inner_self.mutated = True
                    type.__setattr__(
                        DelegatingUncertainty,
                        "summarize",
                        lambda *_args, **_kwargs: None,
                    )
                return retained

        retriever = PublicAtlasRetriever(
            MutatingReference(),
            uncertainty_propagator=DelegatingUncertainty(),
        )
        with self.assertRaisesRegex(ValidationError, "retriever configuration"):
            retriever.retrieve(self.variant, self.context)
        self.assertIs(vars(DelegatingUncertainty)["summarize"], original_summarize)
        self.assertIsNotNone(retriever.retrieve(self.variant, self.context).uncertainty)

    def test_callback_cannot_mutate_known_public_source_graphs(self) -> None:
        retained = self._retained_reference_bundle()
        with tempfile.TemporaryDirectory() as cache_root:
            client = SourceClient(cache_root=cache_root)
            public_reference = PublicReferenceRetriever(client, window_bp=2_000)
            encode = EncodeRestClient(client)
            original_window = public_reference.window_bp
            original_timeout = client.timeout_seconds

            class MutatingInference:
                def __init__(inner_self) -> None:
                    inner_self.calls = 0

                def analyze(inner_self, variant, sequence, *, motifs=()):
                    inner_self.calls += 1
                    if inner_self.calls == 1:
                        public_reference.window_bp = original_window + 1
                    elif inner_self.calls == 2:
                        client.timeout_seconds = original_timeout + 1.0
                    return SequenceInference().analyze(
                        variant,
                        sequence,
                        motifs=motifs,
                    )

            retriever = PublicAtlasRetriever(
                public_reference,
                encode_client=encode,
                sequence_inference=MutatingInference(),
            )
            with self.assertRaisesRegex(ValidationError, "retriever configuration"):
                retriever.retrieve(
                    self.variant,
                    self.context,
                    reference_bundle=retained,
                )
            self.assertEqual(public_reference.window_bp, original_window)

            with self.assertRaisesRegex(ValidationError, "retriever configuration"):
                retriever.retrieve(
                    self.variant,
                    self.context,
                    reference_bundle=retained,
                )
            self.assertEqual(client.timeout_seconds, original_timeout)

            clean = retriever.retrieve(
                self.variant,
                self.context,
                reference_bundle=retained,
            )
            self.assertEqual(clean.variant_id, self.variant.variant_id)

    def test_known_source_guard_allows_operational_limiter_and_callback_counters(self) -> None:
        retained = self._retained_reference_bundle()
        with tempfile.TemporaryDirectory() as cache_root:
            client = SourceClient(cache_root=cache_root)
            encode = EncodeRestClient(client)
            limiter = client._limiters["SRC-ENCODE-REST"]  # noqa: SLF001

            class CountingInference:
                def __init__(inner_self) -> None:
                    inner_self.calls = 0

                def analyze(inner_self, variant, sequence, *, motifs=()):
                    inner_self.calls += 1
                    limiter.wait(max_wait_seconds=0.0)
                    return SequenceInference().analyze(
                        variant,
                        sequence,
                        motifs=motifs,
                    )

            inference = CountingInference()
            result = PublicAtlasRetriever(
                FixedReference(retained),
                encode_client=encode,
                sequence_inference=inference,
            ).retrieve(self.variant, self.context)

            self.assertEqual(result.variant_id, self.variant.variant_id)
            self.assertEqual(inference.calls, 1)
            self.assertGreater(limiter._next_allowed, 0.0)  # noqa: SLF001

    def test_callback_cannot_shadow_or_class_swap_track_graph(self) -> None:
        retained = self._retained_reference_bundle()
        adapter = DeclaredReferenceTrackAdapter.from_rows(
            self._track_metadata("track-callback-guard", "SRC-TRACK-CALLBACK-GUARD"),
            (),
        ).adapter
        holder: list[PublicAtlasRetriever] = []

        class PoisonedAdapter(DeclaredReferenceTrackAdapter):
            __slots__ = ()

        class MutatingReference:
            def __init__(inner_self) -> None:
                inner_self.calls = 0

            def retrieve(inner_self, variant, context, *, window_bp):
                inner_self.calls += 1
                registry = vars(holder[0])["_track_adapters"]
                if inner_self.calls == 1:
                    registry.query_all = lambda *_args, **_kwargs: ()  # type: ignore[attr-defined,method-assign]
                elif inner_self.calls == 2:
                    object.__setattr__(registry.list()[0], "__class__", PoisonedAdapter)
                return retained

        retriever = PublicAtlasRetriever(
            MutatingReference(),
            track_adapters=ReferenceTrackAdapterRegistry((adapter,)),
        )
        holder.append(retriever)
        with self.assertRaisesRegex(ValidationError, "retriever configuration"):
            retriever.retrieve(self.variant, self.context)

        restored_registry = vars(retriever)["_track_adapters"]
        self.assertNotIn("query_all", vars(restored_registry))
        with self.assertRaisesRegex(ValidationError, "retriever configuration"):
            retriever.retrieve(self.variant, self.context)
        restored_registry = vars(retriever)["_track_adapters"]
        self.assertIs(type(restored_registry.list()[0]), DeclaredReferenceTrackAdapter)
        clean = retriever.retrieve(self.variant, self.context)
        self.assertEqual(len(clean.track_reports), 1)

    def test_legacy_marker_and_alias_rebinding_cannot_enable_nested_atlas(self) -> None:
        retained = self._retained_reference_bundle()
        nested_errors: list[ValidationError] = []

        class CountingReference:
            def __init__(inner_self) -> None:
                inner_self.calls = 0

            def retrieve(inner_self, variant, context, *, window_bp):
                inner_self.calls += 1
                return retained

        nested_reference = CountingReference()
        nested = PublicAtlasRetriever(nested_reference)

        class MutatingReference:
            def __init__(inner_self) -> None:
                inner_self.mutated = False

            def retrieve(inner_self, variant, context, *, window_bp):
                if not inner_self.mutated:
                    inner_self.mutated = True
                    atlas_module._ATLAS_CALLBACK_STATE = threading.local()  # type: ignore[attr-defined]
                    atlas_module._ATLAS_CALLBACK_ACTIVE_KEY = "legacy-active"  # type: ignore[attr-defined]
                    atlas_module._ATLAS_CALLBACK_LOCK = threading.RLock()  # type: ignore[attr-defined]
                    vars(atlas_module._ATLAS_CALLBACK_STATE).clear()  # type: ignore[attr-defined]
                    try:
                        nested.retrieve(
                            variant,
                            context,
                            reference_bundle=retained,
                        )
                    except ValidationError as exc:
                        nested_errors.append(exc)
                    atlas_module.atlas_callback_scope = lambda: None  # type: ignore[assignment]
                    try:
                        nested.retrieve(
                            variant,
                            context,
                            reference_bundle=retained,
                        )
                    except ValidationError as exc:
                        nested_errors.append(exc)
                return retained

        retriever = PublicAtlasRetriever(MutatingReference())
        legacy_names = (
            "_ATLAS_CALLBACK_STATE",
            "_ATLAS_CALLBACK_ACTIVE_KEY",
            "_ATLAS_CALLBACK_LOCK",
        )
        try:
            with self.assertRaisesRegex(ValidationError, "package semantic state"):
                retriever.retrieve(self.variant, self.context)
            self.assertEqual(nested_reference.calls, 0)
            self.assertEqual(len(nested_errors), 2)
            self.assertRegex(str(nested_errors[0]), "nested atlas retrieval")
            self.assertRegex(str(nested_errors[1]), "isolation coordinator is invalid")
            self.assertTrue(all(name not in vars(atlas_module) for name in legacy_names))
            self.assertIs(
                atlas_module.atlas_callback_scope,
                atlas_module._callback_isolation_module.atlas_callback_scope,
            )
            clean = retriever.retrieve(self.variant, self.context)
            self.assertEqual(clean.variant_id, self.variant.variant_id)
        finally:
            for name in legacy_names:
                vars(atlas_module).pop(name, None)
            atlas_module.atlas_callback_scope = (
                atlas_module._callback_isolation_module.atlas_callback_scope
            )

    def test_same_thread_nested_atlas_retrieval_is_rejected_before_capture(self) -> None:
        retained = self._retained_reference_bundle()
        nested = PublicAtlasRetriever(FixedReference(retained))
        nested_errors: list[ValidationError] = []

        class NestingReference:
            def retrieve(inner_self, variant, context, *, window_bp):
                try:
                    nested.retrieve(
                        variant,
                        context,
                        reference_bundle=retained,
                    )
                except ValidationError as exc:
                    nested_errors.append(exc)
                return retained

        outer = PublicAtlasRetriever(NestingReference())
        result = outer.retrieve(self.variant, self.context)
        self.assertEqual(result.variant_id, self.variant.variant_id)
        self.assertEqual(len(nested_errors), 1)
        self.assertRegex(str(nested_errors[0]), "nested atlas retrieval")

    def test_atlas_retrievals_serialize_transient_semantic_mutation(self) -> None:
        retained = self._retained_reference_bundle()
        original = atlas_module._SUPPORTED_REFERENCE_FEATURE_TYPES
        first_entered = threading.Event()
        release_first = threading.Event()
        second_entered = threading.Event()
        first_errors: list[BaseException] = []
        second_errors: list[BaseException] = []
        second_results: list[AtlasBundle] = []

        class FirstReference:
            def retrieve(inner_self, variant, context, *, window_bp):
                atlas_module._SUPPORTED_REFERENCE_FEATURE_TYPES = frozenset({"poisoned"})
                first_entered.set()
                release_first.wait(3.0)
                return retained

        class SecondReference:
            def retrieve(inner_self, variant, context, *, window_bp):
                second_entered.set()
                return retained

        first = PublicAtlasRetriever(FirstReference())
        second = PublicAtlasRetriever(SecondReference())

        def run_first() -> None:
            try:
                first.retrieve(self.variant, self.context)
            except BaseException as exc:  # noqa: BLE001 - worker result capture
                first_errors.append(exc)

        def run_second() -> None:
            try:
                second_results.append(second.retrieve(self.variant, self.context))
            except BaseException as exc:  # noqa: BLE001 - worker result capture
                second_errors.append(exc)

        first_thread = threading.Thread(target=run_first)
        second_thread = threading.Thread(target=run_second)
        try:
            first_thread.start()
            self.assertTrue(first_entered.wait(2.0))
            second_thread.start()
            self.assertFalse(second_entered.wait(0.1))
            release_first.set()
            first_thread.join(3.0)
            self.assertTrue(second_entered.wait(2.0))
            second_thread.join(3.0)
        finally:
            release_first.set()
            atlas_module._SUPPORTED_REFERENCE_FEATURE_TYPES = original
            first_thread.join(3.0)
            second_thread.join(3.0)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())
        self.assertEqual(len(first_errors), 1)
        self.assertIsInstance(first_errors[0], ValidationError)
        self.assertEqual(second_errors, [])
        self.assertEqual(len(second_results), 1)
        self.assertIs(
            atlas_module._SUPPORTED_REFERENCE_FEATURE_TYPES,
            original,
        )

    def test_projection_limitations_keeps_overflow_marker_unique(self) -> None:
        message = "projection payload was compacted"
        with patch.object(atlas_module, "_HARD_LIMITATIONS", 3):
            selected = atlas_module._projection_limitations(
                (message, "first limitation", "second limitation", "third limitation"),
                message,
            )
        self.assertEqual(
            selected,
            ("first limitation", "second limitation", message),
        )
        self.assertEqual(len(selected), len(set(selected)))

    def test_large_sequence_and_track_artifacts_compact_and_replay(self) -> None:
        # Lower the private ceiling only inside this regression so ordinary retained
        # artifacts exercise the same production compaction path without a huge fixture.
        with patch.object(atlas_module, "_HARD_OBSERVATION_PAYLOAD_BYTES", 700):
            result = self._full_nested_atlas_bundle()
            sequence_observation = next(
                item for item in result.observations if item.feature_type == "motif_delta"
            )
            track_observation = next(
                item
                for item in result.observations
                if item.feature_type.startswith("reference_track:")
            )
            for observation, omitted_key in (
                (sequence_observation, "analysis"),
                (track_observation, "report"),
            ):
                with self.subTest(feature_type=observation.feature_type):
                    self.assertEqual(observation.state, EvidenceState.ABSTAINED)
                    self.assertEqual(
                        observation.payload["projection"],
                        "omitted_over_atlas_observation_payload_ceiling",
                    )
                    self.assertNotIn(omitted_key, observation.payload)
            self.assertIsNotNone(result.sequence_analysis)
            self.assertEqual(len(result.track_reports), 1)

            retained = self._retained_reference_bundle()
            reopened = AtlasBundle.from_dict(
                result.to_dict(),
                self.variant,
                self.context,
                reference_bundle=retained,
                replay_inputs=result.replay_inputs,
            )
            self.assertEqual(reopened.to_dict(), result.to_dict())
            compact_claims = {
                item.channel: item
                for item in reopened.to_evidence_claims(
                    variant=self.variant,
                    context=self.context,
                )
                if item.channel == "motif_delta"
                or item.channel.startswith("reference_track:")
            }
            self.assertEqual(compact_claims["motif_delta"].state, EvidenceState.ABSTAINED)
            self.assertEqual(
                compact_claims[track_observation.feature_type].state,
                EvidenceState.ABSTAINED,
            )

    def test_structural_atlas_creation_cannot_bypass_derivation_replay_for_claims(self) -> None:
        retained = StubReferenceRetriever().retrieve(
            self.variant,
            self.context,
            window_bp=2_000,
        )
        valid = PublicAtlasRetriever(FixedReference(retained)).retrieve(
            self.variant,
            self.context,
        )
        fabricated = AtlasObservation(
            observation_id="fabricated-supported-observation",
            source_id="SRC-ENSEMBL-REST",
            feature_type="reference_regulatory",
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.REFERENCE,
            summary="Fabricated structural observation.",
            payload={"fabricated": True},
            context_key=self.context.key,
            context_score=None,
            receipt=None,
        )
        structural = AtlasBundle.create(
            variant=self.variant,
            context=self.context,
            query=valid.query,
            source_bundle_address=retained.content_address,
            replay_inputs=valid.replay_inputs,
            observations=(*valid.observations, fabricated),
            receipts=valid.receipts,
            warnings=valid.warnings,
            sequence_analysis=valid.sequence_analysis,
            uncertainty=None,
            track_reports=valid.track_reports,
        )
        with self.assertRaisesRegex(ValidationError, "replay-verified reference bundle"):
            structural.to_evidence_claims(variant=self.variant, context=self.context)

        attached = AtlasBundle.create(
            variant=self.variant,
            context=self.context,
            query=valid.query,
            source_bundle_address=retained.content_address,
            replay_inputs=valid.replay_inputs,
            observations=(*valid.observations, fabricated),
            receipts=valid.receipts,
            warnings=valid.warnings,
            sequence_analysis=valid.sequence_analysis,
            uncertainty=None,
            track_reports=valid.track_reports,
            reference_bundle=retained,
        )
        with self.assertRaisesRegex(ValidationError, "observations do not exactly reconstruct"):
            attached.to_evidence_claims(variant=self.variant, context=self.context)

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
            context=self.context,
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

    def test_sequence_work_ceiling_counts_both_sequences_and_applicable_strands(self) -> None:
        class ForbiddenInference(SequenceInference):
            def __init__(inner_self) -> None:
                super().__init__()
                inner_self.calls = 0

            def analyze(inner_self, variant, sequence, *, motifs=()):
                inner_self.calls += 1
                raise AssertionError("over-limit motif inference must not execute")

        sequence_length = 50_000
        motif = MotifDefinition(
            "overlapping-non-palindromic",
            "overlapping non-palindromic IUPAC motif",
            "WN",
        )
        windows_per_sequence = sequence_length - len(motif.pattern) + 1
        old_preflight_potential_hits = windows_per_sequence * 2
        exact_raw_hit_ceiling = windows_per_sequence * 2 * 2
        self.assertLessEqual(
            old_preflight_potential_hits,
            atlas_module.MAX_ATLAS_POTENTIAL_MOTIF_HITS,
        )
        self.assertGreater(
            exact_raw_hit_ceiling,
            atlas_module.MAX_ATLAS_POTENTIAL_MOTIF_HITS,
        )
        self.assertEqual(exact_raw_hit_ceiling, 199_996)

        sequence_receipt = _receipt("SRC-UCSC-REST", "two-sequence-strand-ceiling")
        feature_receipt = _receipt("SRC-ENSEMBL-REST", "two-sequence-strand-features")
        sequence = SequenceSlice(
            assembly=self.context.genome_build,
            chromosome=self.variant.chromosome,
            start=self.variant.start,
            end=self.variant.start + sequence_length - 1,
            sequence="A" * sequence_length,
            source_id="SRC-UCSC-REST",
            receipt=sequence_receipt,
        )
        bundle = ReferenceBundle.create(
            variant_id=self.variant.variant_id,
            context=self.context,
            sequence=sequence,
            elements=(),
            raw_features=(),
            receipts=(sequence_receipt, feature_receipt),
            warnings=(),
        )
        inference = ForbiddenInference()

        result = PublicAtlasRetriever(
            FixedReference(bundle),
            sequence_inference=inference,
            motifs=(motif,),
        ).retrieve(
            self.variant,
            self.context,
            query=AtlasQuery(
                variant_id=self.variant.variant_id,
                window_bp=100_000,
            ),
        )

        self.assertEqual(inference.calls, 0)
        self.assertIsNone(result.sequence_analysis)
        self.assertIn(atlas_module._MOTIF_WORK_CEILING_WARNING, result.warnings)
        observation = next(
            item for item in result.observations if item.feature_type == "motif_delta"
        )
        self.assertEqual(observation.state, EvidenceState.ABSTAINED)

    def _coherently_rebuild(
        self,
        source: AtlasBundle,
        *,
        observations: tuple[AtlasObservation, ...],
        sequence_analysis: SequenceAnalysisResult | None,
        track_reports: tuple[ReferenceTrackQueryReport, ...],
    ) -> AtlasBundle:
        self.assertIsNone(source.replay_inputs.domain_profile)
        provisional = AtlasBundle.create(
            variant=self.variant,
            context=self.context,
            query=source.query,
            source_bundle_address=source.source_bundle_address,
            replay_inputs=source.replay_inputs,
            observations=observations,
            receipts=source.receipts,
            warnings=source.warnings,
            sequence_analysis=sequence_analysis,
            track_reports=track_reports,
        )
        uncertainty = UncertaintyPropagator().summarize(
            provisional._to_evidence_claims_unchecked(
                variant=self.variant,
                context=self.context,
            )
        )
        return AtlasBundle.create(
            variant=self.variant,
            context=self.context,
            query=source.query,
            source_bundle_address=source.source_bundle_address,
            replay_inputs=source.replay_inputs,
            observations=observations,
            receipts=source.receipts,
            warnings=source.warnings,
            sequence_analysis=sequence_analysis,
            uncertainty=uncertainty,
            track_reports=track_reports,
        )

    def _empty_reference(self):
        class EmptyReference:
            def retrieve(inner_self, variant, context, *, window_bp=None):
                return ReferenceBundle.create(
                    variant_id=variant.variant_id,
                    context=context,
                    sequence=None,
                    elements=(),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )

        return EmptyReference()

    def _full_nested_atlas_bundle(self) -> AtlasBundle:
        adapter = DeclaredReferenceTrackAdapter.from_rows(
            self._track_metadata("track-round-trip", "SRC-TRACK-ROUND-TRIP"),
            (
                {
                    "record_id": "round-trip-row",
                    "chromosome": self.variant.chromosome,
                    "start": self.variant.start,
                    "end": self.variant.end,
                    "context_key": self.context.key,
                    "payload": {"signal": 0.75},
                },
            ),
        ).adapter
        return PublicAtlasRetriever(
            FixedReference(self._retained_reference_bundle()),
            track_adapters=ReferenceTrackAdapterRegistry((adapter,)),
        ).retrieve(self.variant, self.context)

    def _retained_reference_bundle(self) -> ReferenceBundle:
        return StubReferenceRetriever().retrieve(
            self.variant,
            self.context,
            window_bp=2_000,
        )

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
