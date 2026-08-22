"""Depth checks for disease ontology context resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context import ContextResolution, ContextResolutionState
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierDiseaseCandidate:
    candidate_id: str
    label: str
    evidence_count: int
    source_count: int
    mean_confidence: float
    quality: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.candidate_id
            or not self.label
            or self.evidence_count < 1
            or self.source_count < 1
        ):
            raise ValidationError("disease candidate depth row is incomplete")
        if not 0.0 <= self.mean_confidence <= 1.0:
            raise ValidationError("disease candidate confidence is invalid")
        if self.quality not in {"strong", "moderate", "weak"}:
            raise ValidationError("disease candidate quality is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierDiseaseDepthReport:
    context_key: str
    state: str
    selected_candidate_id: str | None
    candidates: tuple[CellContextFrontierDiseaseCandidate, ...]
    source_ids: tuple[str, ...]
    evidence_count: int
    ambiguity_margin: float | None
    review_required: bool
    limitations: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.context_key or not self.limitations:
            raise ValidationError("disease depth report is incomplete")
        if self.ambiguity_margin is not None and self.ambiguity_margin < 0:
            raise ValidationError("disease ambiguity margin cannot be negative")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"candidate_count": self.candidate_count}


def profile_disease_context_resolution(
    resolution: ContextResolution,
) -> CellContextFrontierDiseaseDepthReport:
    candidates = tuple(
        CellContextFrontierDiseaseCandidate(
            candidate.candidate_id,
            candidate.candidate_label,
            candidate.observation_count,
            len(candidate.source_ids),
            candidate.mean_confidence,
            "strong"
            if candidate.mean_confidence >= 0.85
            else "moderate"
            if candidate.mean_confidence >= 0.6
            else "weak",
        )
        for candidate in resolution.candidates
    )
    ordered = sorted(item.mean_confidence for item in candidates)
    margin = None if len(ordered) < 2 else round(ordered[-1] - ordered[-2], 6)
    review_required = resolution.state in {
        ContextResolutionState.AMBIGUOUS,
        ContextResolutionState.CONTRADICTORY,
        ContextResolutionState.OUT_OF_DOMAIN,
        ContextResolutionState.ABSTAINED,
    }
    return CellContextFrontierDiseaseDepthReport(
        resolution.context_key,
        resolution.state.value,
        resolution.selected_candidate_id,
        candidates,
        resolution.source_ids,
        len(resolution.evidence_ids),
        margin,
        review_required,
        resolution.limitations + ("Ontology term mapping is not a disease conclusion.",),
        resolution.state is ContextResolutionState.SUPPORTED and bool(candidates),
    )


__all__ = [
    "CellContextFrontierDiseaseCandidate",
    "CellContextFrontierDiseaseDepthReport",
    "profile_disease_context_resolution",
]
