"""Depth checks that keep molecular class and molecular state separate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context import ContextResolution, ContextResolutionState, MolecularClassStateResolution
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierMolecularDimension:
    dimension: str
    state: str
    selected_candidate_id: str | None
    candidate_ids: tuple[str, ...]
    evidence_count: int
    source_ids: tuple[str, ...]
    uncertainty: float
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.dimension not in {"molecular_class", "molecular_state"}:
            raise ValidationError("molecular dimension name is invalid")
        if not 0.0 <= self.uncertainty <= 1.0 or self.evidence_count < 0:
            raise ValidationError("molecular dimension range is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierMolecularDepthReport:
    context_key: str
    state: str
    molecular_class: CellContextFrontierMolecularDimension
    molecular_state: CellContextFrontierMolecularDimension
    disagreement: bool
    missing_dimension: bool
    review_required: bool
    limitations: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.context_key or not self.limitations:
            raise ValidationError("molecular depth report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _dimension(name: str, resolution: ContextResolution) -> CellContextFrontierMolecularDimension:
    return CellContextFrontierMolecularDimension(
        name,
        resolution.state.value,
        resolution.selected_candidate_id,
        tuple(item.candidate_id for item in resolution.candidates),
        len(resolution.evidence_ids),
        resolution.source_ids,
        resolution.uncertainty,
    )


def profile_molecular_context_resolution(
    resolution: MolecularClassStateResolution,
) -> CellContextFrontierMolecularDepthReport:
    class_dimension = _dimension("molecular_class", resolution.molecular_class)
    state_dimension = _dimension("molecular_state", resolution.molecular_state)
    disagreement = class_dimension.state != state_dimension.state
    missing_dimension = (
        class_dimension.state == ContextResolutionState.ABSTAINED.value
        or state_dimension.state == ContextResolutionState.ABSTAINED.value
    )
    review_required = (
        resolution.state is not ContextResolutionState.SUPPORTED
        or disagreement
        or missing_dimension
    )
    return CellContextFrontierMolecularDepthReport(
        resolution.context_key,
        resolution.state.value,
        class_dimension,
        state_dimension,
        disagreement,
        missing_dimension,
        review_required,
        resolution.limitations
        + ("Molecular class and state are context descriptors, not actionability conclusions.",),
        resolution.state is ContextResolutionState.SUPPORTED and not disagreement,
    )


__all__ = [
    "CellContextFrontierMolecularDepthReport",
    "CellContextFrontierMolecularDimension",
    "profile_molecular_context_resolution",
]
