"""Context-qualified atlas evidence contracts for the seven atlas roles."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .context import compare_context, context_gate
from .errors import ValidationError
from .models import EvidenceClaim, EvidenceState, EvidenceTier, ReferenceContext
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ContextObservation:
    """One source-scoped observation before case-context transport."""

    observation_id: str
    source_id: str
    source_version: str
    context: ReferenceContext
    channel: str
    state: EvidenceState
    tier: EvidenceTier
    score: float | None
    confidence: float
    summary: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "source_id",
            "source_version",
            "channel",
            "summary",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"context observation {name} is required")
        if self.score is not None and not 0.0 <= self.score <= 1.0:
            raise ValidationError("context observation score must be between 0 and 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("context observation confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextEvidenceBundle:
    """Transported atlas observations with context matches retained per claim."""

    variant_id: str
    edge_id: str
    context: ReferenceContext
    claims: tuple[EvidenceClaim, ...]
    matched_count: int
    out_of_context_count: int
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContextEvidenceBuilder:
    """Build atlas claims without transferring incompatible context silently."""

    def build(
        self,
        variant_id: str,
        edge_id: str,
        case_context: ReferenceContext,
        observations: Iterable[ContextObservation],
        *,
        minimum_context_score: float = 0.35,
        produced_by: str = "context_evidence_builder",
    ) -> ContextEvidenceBundle:
        if not variant_id.strip() or not edge_id.strip():
            raise ValidationError("variant_id and edge_id are required")
        if not 0.0 <= minimum_context_score <= 1.0:
            raise ValidationError("minimum_context_score must be between 0 and 1")
        claims: list[EvidenceClaim] = []
        warnings: list[str] = []
        matched = 0
        out_of_context = 0
        for observation in observations:
            match = compare_context(case_context, observation.context)
            usable = context_gate(match, minimum=minimum_context_score)
            if usable:
                matched += 1
            else:
                out_of_context += 1
                warnings.append(
                    f"{observation.observation_id} is below context threshold "
                    f"({match.score:.3f} < {minimum_context_score:.3f})."
                )
            claim_state = observation.state
            if not usable and claim_state == EvidenceState.SUPPORTED:
                claim_state = EvidenceState.OUT_OF_DOMAIN
            claim = EvidenceClaim(
                evidence_id=f"atlas-context:{observation.observation_id}",
                edge_id=edge_id,
                source_id=observation.source_id,
                channel=observation.channel,
                state=claim_state,
                tier=observation.tier,
                score=observation.score if usable else None,
                confidence=round(observation.confidence * match.score, 6),
                context=case_context,
                summary=observation.summary,
                payload={
                    "observation": observation.to_dict(),
                    "context_match": match.to_dict(),
                    "source_version": observation.source_version,
                },
                produced_by=produced_by,
            )
            claims.append(claim)
        if not claims:
            warnings.append("No atlas observations were supplied; no context claim was created.")
        payload = {
            "variant_id": variant_id,
            "edge_id": edge_id,
            "context": case_context,
            "claims": claims,
            "matched_count": matched,
            "out_of_context_count": out_of_context,
            "warnings": tuple(dict.fromkeys(warnings)),
        }
        return ContextEvidenceBundle(
            variant_id=variant_id,
            edge_id=edge_id,
            context=case_context,
            claims=tuple(claims),
            matched_count=matched,
            out_of_context_count=out_of_context,
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(payload),
        )


ATLAS_ROLE_CHANNELS: dict[str, str] = {
    "A16": "brain_context",
    "A17": "glioma_cell_state",
    "A18": "chromatin",
    "A19": "methylation",
    "A20": "contact",
    "A21": "literature",
    "A22": "functional",
}
