"""Deterministic evidence adapters used by the initial vertical slice."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .context import ContextMatch, compare_context
from .identity import interval_distance, variant_interval
from .models import (
    CandidateElement,
    EvidenceState,
    EvidenceTier,
    EvidenceClaim,
    ReferenceContext,
    VariantIdentity,
)
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class FeatureReading:
    """A bounded numerical input with an explicit state."""

    channel: str
    value: float | None
    confidence: float
    state: EvidenceState
    source_id: str
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "channel": self.channel,
            "value": self.value,
            "confidence": self.confidence,
            "state": self.state.value,
            "source_id": self.source_id,
            "rationale": self.rationale,
        }


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """Clamp a numeric observation into the contract range."""

    return round(max(minimum, min(maximum, float(value))), 6)


def sigmoid(value: float) -> float:
    """Numerically stable logistic transform for bounded derived scores."""

    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def reading_from_feature(
    channel: str,
    raw_value: Any,
    *,
    source_id: str,
    confidence: float = 0.7,
) -> FeatureReading:
    """Convert adapter output to a stateful reading without inventing missing values."""

    if raw_value is None:
        return FeatureReading(
            channel=channel,
            value=None,
            confidence=0.15,
            state=EvidenceState.UNSUPPORTED,
            source_id=source_id,
            rationale="No value was supplied by the adapter.",
        )
    value = clamp(float(raw_value))
    if value <= 0.15:
        state = EvidenceState.MEASURED_NEGATIVE
        rationale = "Input value is a measured low-support observation."
    else:
        state = EvidenceState.SUPPORTED
        rationale = "Input value passed the deterministic support threshold."
    return FeatureReading(
        channel=channel,
        value=value,
        confidence=clamp(confidence),
        state=state,
        source_id=source_id,
        rationale=rationale,
    )


def element_relevance(variant: VariantIdentity, element: CandidateElement) -> tuple[float, str]:
    """Compute a transparent proximity prior, never a causal claim."""

    distance = interval_distance(variant_interval(variant), (element.chromosome, element.start, element.end))
    if distance is None:
        return 0.0, "Different contigs; no proximity prior."
    if distance == 0:
        return 1.0, "Variant overlaps the candidate element interval."
    scale = float(element.annotations.get("proximity_scale", 250_000.0))
    scale = max(scale, 1.0)
    value = clamp(math.exp(-distance / scale))
    return value, f"Distance-based prior at {distance} bp; not a target-gene claim."


def feature_readings(element: CandidateElement) -> tuple[FeatureReading, ...]:
    """Read supported numeric channels from an element manifest."""

    channel_sources = {
        "motif_delta": "sequence",
        "sequence_model": "sequence_model",
        "conservation": "conservation",
        "accessibility": "chromatin",
        "histone_activity": "chromatin",
        "methylation": "methylation",
        "contact_strength": "topology",
        "boundary_support": "topology",
        "qtl_support": "linking",
        "coaccessibility": "linking",
        "perturbation_support": "functional",
        "state_prior": "state_atlas",
        "cohort_recurrence": "cohort",
    }
    readings: list[FeatureReading] = []
    for feature_name, source_suffix in channel_sources.items():
        if feature_name not in element.features:
            continue
        readings.append(
            reading_from_feature(
                feature_name,
                element.features[feature_name],
                source_id=f"{element.source_id}:{source_suffix}",
                confidence=float(element.annotations.get(f"{feature_name}_confidence", 0.7)),
            )
        )
    if not readings:
        readings.append(
            reading_from_feature(
                "element_support",
                None,
                source_id=element.source_id,
            )
        )
    return tuple(readings)


def claim_id(edge_id: str, channel: str, source_id: str) -> str:
    """Create a stable short identifier for a claim."""

    digest = content_hash({"edge": edge_id, "channel": channel, "source": source_id}).split(":", 1)[1]
    return f"ev-{digest[:20]}"


def make_claim(
    *,
    edge_id: str,
    reading: FeatureReading,
    context: ReferenceContext,
    context_match: ContextMatch,
    summary: str,
    payload: Mapping[str, Any] | None = None,
    depends_on: Iterable[str] = (),
    tier: EvidenceTier = EvidenceTier.COMPUTED,
) -> EvidenceClaim:
    """Build a typed claim while carrying context transport metadata."""

    adjusted_confidence = clamp(reading.confidence * context_match.score)
    if reading.state == EvidenceState.SUPPORTED and context_match.score < 0.35:
        state = EvidenceState.OUT_OF_DOMAIN
    else:
        state = reading.state
    return EvidenceClaim(
        evidence_id=claim_id(edge_id, reading.channel, reading.source_id),
        edge_id=edge_id,
        source_id=reading.source_id,
        channel=reading.channel,
        state=state,
        tier=tier,
        score=reading.value,
        confidence=adjusted_confidence,
        context=context,
        summary=summary,
        payload=dict(payload or {}) | {"context_match": context_match.to_dict(), "reading": reading.to_dict()},
        depends_on=tuple(depends_on),
    )


def derived_path_score(edge_scores: Iterable[float]) -> float:
    """Combine causal edges conservatively; a weak edge remains visible."""

    scores = [clamp(value) for value in edge_scores]
    if not scores:
        return 0.0
    product = 1.0
    for score in scores:
        product *= score
    arithmetic = sum(scores) / len(scores)
    return clamp(0.65 * (product ** (1.0 / len(scores))) + 0.35 * arithmetic)


def context_for_element(case_context: ReferenceContext, element: CandidateElement) -> ContextMatch:
    """Compare a candidate element's source context to the case context."""

    return compare_context(case_context, element.context)
