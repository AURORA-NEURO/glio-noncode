"""Context-aware public atlas observations and evidence conversion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .data_sources import (
    FetchReceipt,
    PublicReferenceRetriever,
    ReferenceBundle,
    SourcePayload,
)
from .errors import SourceError, ValidationError
from .models import EvidenceClaim, EvidenceState, EvidenceTier, ReferenceContext, VariantIdentity
from .serialization import content_hash, jsonable


class ReferenceBundleProvider(Protocol):
    def retrieve(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        window_bp: int | None = None,
    ) -> ReferenceBundle: ...


class EncodeProvider(Protocol):
    def search_experiments(
        self,
        *,
        assay_title: str | None = None,
        biosample_ontology_term_name: str | None = None,
        organism: str = "Homo sapiens",
        limit: int = 25,
    ) -> SourcePayload: ...


@dataclass(frozen=True, slots=True)
class AtlasQuery:
    """Bounded public-atlas request."""

    variant_id: str
    window_bp: int = 2_000
    include_encode_catalog: bool = False
    encode_assay_title: str | None = None
    encode_biosample: str | None = None
    encode_limit: int = 25

    def __post_init__(self) -> None:
        if not self.variant_id.strip():
            raise ValidationError("atlas query requires variant_id")
        if self.window_bp < 1 or self.window_bp > 5_000_000:
            raise ValidationError("atlas window_bp must be between 1 and 5000000")
        if self.encode_limit < 1 or self.encode_limit > 1000:
            raise ValidationError("atlas encode_limit must be between 1 and 1000")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasObservation:
    """One source-scoped observation with limitations and retrieval receipt."""

    observation_id: str
    source_id: str
    feature_type: str
    state: EvidenceState
    tier: EvidenceTier
    summary: str
    payload: Mapping[str, Any]
    context_key: str
    context_score: float | None
    receipt: FetchReceipt | None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("observation_id", "source_id", "feature_type", "summary", "context_key"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"atlas {name} must not be empty")
        if self.context_score is not None and not 0.0 <= self.context_score <= 1.0:
            raise ValidationError("atlas context_score must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasBundle:
    """All public observations for one variant and declared context."""

    variant_id: str
    context_key: str
    observations: tuple[AtlasObservation, ...]
    receipts: tuple[FetchReceipt, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def abstained_count(self) -> int:
        return sum(
            observation.state == EvidenceState.ABSTAINED for observation in self.observations
        )

    def to_evidence_claims(
        self,
        *,
        variant: VariantIdentity,
        context: ReferenceContext,
        edge_id: str | None = None,
    ) -> tuple[EvidenceClaim, ...]:
        """Convert observations to reference claims without inventing scores."""

        claims: list[EvidenceClaim] = []
        edge = edge_id or f"{variant.variant_id}:atlas"
        for observation in self.observations:
            claims.append(
                EvidenceClaim(
                    evidence_id=f"{self.content_address}:{observation.observation_id}",
                    edge_id=edge,
                    source_id=observation.source_id,
                    channel=observation.feature_type,
                    state=observation.state,
                    tier=observation.tier,
                    score=None,
                    confidence=1.0 if observation.state != EvidenceState.ABSTAINED else 0.0,
                    context=context,
                    summary=observation.summary,
                    payload={
                        "observation": observation.to_dict(),
                        "interpretation_boundary": (
                            "reference observation; not disease-specific mechanism evidence"
                        ),
                    },
                    produced_by="public_atlas_retriever",
                )
            )
        return tuple(claims)


class PublicAtlasRetriever:
    """Orchestrate real public retrieval while preserving source boundaries."""

    def __init__(
        self,
        reference_retriever: ReferenceBundleProvider | None = None,
        encode_client: EncodeProvider | None = None,
    ) -> None:
        self.reference_retriever = reference_retriever or PublicReferenceRetriever()
        self.encode_client = encode_client

    def retrieve(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        query: AtlasQuery | None = None,
    ) -> AtlasBundle:
        selected_query = query or AtlasQuery(variant_id=variant.variant_id)
        if selected_query.variant_id != variant.variant_id:
            raise ValidationError("atlas query variant_id does not match variant")
        bundle = self.reference_retriever.retrieve(
            variant,
            context,
            window_bp=selected_query.window_bp,
        )
        observations: list[AtlasObservation] = []
        receipts: list[FetchReceipt] = list(bundle.receipts)
        warnings: list[str] = list(bundle.warnings)
        observations.extend(self._sequence_observation(bundle, context))
        observations.extend(self._feature_observations(bundle, context))
        if selected_query.include_encode_catalog:
            if self.encode_client is None:
                observations.append(
                    AtlasObservation(
                        observation_id="encode-catalog-unconfigured",
                        source_id="SRC-ENCODE-REST",
                        feature_type="assay_catalog",
                        state=EvidenceState.ABSTAINED,
                        tier=EvidenceTier.REFERENCE,
                        summary="ENCODE catalog was requested but no ENCODE client was configured.",
                        payload={},
                        context_key=context.key,
                        context_score=None,
                        receipt=None,
                        limitations=("No ENCODE request was attempted.",),
                    )
                )
            else:
                try:
                    encode_payload = self.encode_client.search_experiments(
                        assay_title=selected_query.encode_assay_title,
                        biosample_ontology_term_name=selected_query.encode_biosample,
                        limit=selected_query.encode_limit,
                    )
                    receipts.append(encode_payload.receipt)
                    observations.append(self._encode_observation(encode_payload, context))
                except SourceError as error:
                    receipt = getattr(error, "receipt", None)
                    if receipt is not None:
                        receipts.append(receipt)
                    warnings.append(f"ENCODE catalog retrieval abstained: {error}")
                    observations.append(
                        AtlasObservation(
                            observation_id="encode-catalog-failure",
                            source_id="SRC-ENCODE-REST",
                            feature_type="assay_catalog",
                            state=EvidenceState.ABSTAINED,
                            tier=EvidenceTier.REFERENCE,
                            summary=(
                                "ENCODE catalog retrieval failed; no assay availability "
                                "conclusion was made."
                            ),
                            payload={},
                            context_key=context.key,
                            context_score=None,
                            receipt=receipt,
                            limitations=(
                                str(error),
                                "A source failure is not a negative measurement.",
                            ),
                        )
                    )
        payload = {
            "variant_id": variant.variant_id,
            "context_key": context.key,
            "observations": observations,
            "receipts": receipts,
            "warnings": warnings,
        }
        return AtlasBundle(
            variant_id=variant.variant_id,
            context_key=context.key,
            observations=tuple(observations),
            receipts=tuple(receipts),
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(payload),
        )

    @staticmethod
    def _sequence_observation(
        bundle: ReferenceBundle, context: ReferenceContext
    ) -> tuple[AtlasObservation, ...]:
        if bundle.sequence is None:
            return (
                AtlasObservation(
                    observation_id="reference-sequence-abstained",
                    source_id="SRC-UCSC-REST",
                    feature_type="reference_sequence",
                    state=EvidenceState.ABSTAINED,
                    tier=EvidenceTier.REFERENCE,
                    summary="Reference sequence retrieval abstained for this interval.",
                    payload={},
                    context_key=context.key,
                    context_score=None,
                    receipt=next(
                        (
                            receipt
                            for receipt in bundle.receipts
                            if receipt.source_id == "SRC-UCSC-REST"
                        ),
                        None,
                    ),
                    limitations=("The missing sequence is not treated as a sequence negative.",),
                ),
            )
        sequence = bundle.sequence
        return (
            AtlasObservation(
                observation_id=f"sequence:{sequence.start}-{sequence.end}",
                source_id=sequence.source_id,
                feature_type="reference_sequence",
                state=EvidenceState.SUPPORTED,
                tier=EvidenceTier.REFERENCE,
                summary=(
                    f"Public reference sequence retrieved for "
                    f"{sequence.chromosome}:{sequence.start}-{sequence.end}."
                ),
                payload={
                    "assembly": sequence.assembly,
                    "chromosome": sequence.chromosome,
                    "start": sequence.start,
                    "end": sequence.end,
                    "sequence_hash": content_hash(sequence.sequence),
                    "sequence_length": len(sequence.sequence),
                },
                context_key=context.key,
                context_score=1.0,
                receipt=sequence.receipt,
                limitations=(
                    (
                        "Reference sequence availability does not establish regulatory "
                        "activity or disease mechanism."
                    ),
                ),
            ),
        )

    @staticmethod
    def _feature_observations(
        bundle: ReferenceBundle, context: ReferenceContext
    ) -> list[AtlasObservation]:
        observations: list[AtlasObservation] = []
        for index, feature in enumerate(bundle.raw_features):
            feature_type = str(
                feature.get("feature_type") or feature.get("object_type") or "annotation"
            )
            feature_id = str(feature.get("id") or feature.get("stable_id") or index)
            source_id = "SRC-ENSEMBL-REST"
            observations.append(
                AtlasObservation(
                    observation_id=f"ensembl:{feature_type}:{feature_id}",
                    source_id=source_id,
                    feature_type=f"reference_{feature_type.lower()}",
                    state=EvidenceState.SUPPORTED,
                    tier=EvidenceTier.REFERENCE,
                    summary=(
                        f"Ensembl returned {feature_type} annotation {feature_id} "
                        "in the queried interval."
                    ),
                    payload=dict(feature),
                    context_key=context.key,
                    context_score=None,
                    receipt=next(
                        (receipt for receipt in bundle.receipts if receipt.source_id == source_id),
                        None,
                    ),
                    limitations=(
                        (
                            "Generic reference annotation is not a glioma-state or "
                            "functional activity measurement."
                        ),
                    ),
                )
            )
        if not observations:
            observations.append(
                AtlasObservation(
                    observation_id="ensembl:no-overlap",
                    source_id="SRC-ENSEMBL-REST",
                    feature_type="reference_annotation",
                    state=EvidenceState.ABSENT,
                    tier=EvidenceTier.REFERENCE,
                    summary=(
                        "No supported Ensembl feature types were returned for the queried interval."
                    ),
                    payload={"raw_feature_count": 0},
                    context_key=context.key,
                    context_score=None,
                    receipt=next(
                        (
                            receipt
                            for receipt in bundle.receipts
                            if receipt.source_id == "SRC-ENSEMBL-REST"
                        ),
                        None,
                    ),
                    limitations=(
                        (
                            "No-overlap in this endpoint is not a negative regulatory "
                            "activity measurement."
                        ),
                    ),
                )
            )
        return observations

    @staticmethod
    def _encode_observation(payload: SourcePayload, context: ReferenceContext) -> AtlasObservation:
        value = payload.value
        rows: list[Mapping[str, Any]] = []
        if isinstance(value, Mapping):
            graph = value.get("@graph")
            if isinstance(graph, list):
                rows = [row for row in graph if isinstance(row, Mapping)]
            else:
                rows = [value]
        return AtlasObservation(
            observation_id=f"encode:catalog:{payload.receipt.response_hash or 'unknown'}",
            source_id="SRC-ENCODE-REST",
            feature_type="assay_catalog",
            state=EvidenceState.SUPPORTED if rows else EvidenceState.ABSENT,
            tier=EvidenceTier.REFERENCE,
            summary=(
                f"ENCODE returned {len(rows)} experiment metadata records for the "
                "declared catalog query."
            ),
            payload={
                "record_count": len(rows),
                "accessions": [str(row.get("accession")) for row in rows if row.get("accession")],
            },
            context_key=context.key,
            context_score=None,
            receipt=payload.receipt,
            limitations=(
                (
                    "Catalog metadata does not establish that an experiment measured "
                    "this variant or interval."
                ),
            ),
        )
