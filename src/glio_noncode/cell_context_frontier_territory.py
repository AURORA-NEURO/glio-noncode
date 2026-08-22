"""Depth checks for territory candidates and assembled context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context import ContextResolution, ContextResolutionState, GliomaStateContext
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierTerritoryCandidate:
    candidate_id: str
    label: str
    evidence_count: int
    source_ids: tuple[str, ...]
    support_fraction: float
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.label or self.evidence_count < 1:
            raise ValidationError("territory candidate is incomplete")
        if not 0.0 <= self.support_fraction <= 1.0:
            raise ValidationError("territory support fraction is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierTerritoryDepthReport:
    context_key: str
    state: str
    candidates: tuple[CellContextFrontierTerritoryCandidate, ...]
    assembled_state: str | None
    component_states: dict[str, str]
    one_to_many: bool
    weakest_component: str
    review_required: bool
    limitations: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.context_key or not self.component_states or not self.weakest_component:
            raise ValidationError("territory depth report is incomplete")
        if not self.limitations:
            raise ValidationError("territory depth report needs limitations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"candidate_count": self.candidate_count}


def profile_territory_context_resolution(
    resolution: ContextResolution, assembled: GliomaStateContext | None = None
) -> CellContextFrontierTerritoryDepthReport:
    candidates = tuple(
        CellContextFrontierTerritoryCandidate(
            item.candidate_id,
            item.candidate_label,
            item.observation_count,
            item.source_ids,
            min(1.0, item.mean_confidence),
        )
        for item in resolution.candidates
    )
    component_states = {"territory": resolution.state.value}
    if assembled is not None:
        component_states.update(
            {
                "disease": assembled.disease.state.value,
                "age_route": assembled.age_route.state.value,
                "molecular": assembled.molecular.state.value,
                "assembled": assembled.state.value,
            }
        )
    weakest = min(
        component_states,
        key=lambda key: {
            "supported": 0,
            "ambiguous": 1,
            "contradictory": 2,
            "abstained": 3,
            "out_of_domain": 4,
        }.get(component_states[key], 5),
    )
    return CellContextFrontierTerritoryDepthReport(
        resolution.context_key,
        resolution.state.value,
        candidates,
        None if assembled is None else assembled.state.value,
        component_states,
        len(candidates) > 1,
        weakest,
        len(candidates) > 1
        or resolution.state is not ContextResolutionState.SUPPORTED
        or (assembled is not None and assembled.state is not ContextResolutionState.SUPPORTED),
        resolution.limitations
        + (
            "Territory is an evidence dimension and does not establish malignant "
            "identity clinically.",
        ),
        resolution.state is ContextResolutionState.SUPPORTED
        and (assembled is None or assembled.state is ContextResolutionState.SUPPORTED),
    )


__all__ = [
    "CellContextFrontierTerritoryCandidate",
    "CellContextFrontierTerritoryDepthReport",
    "profile_territory_context_resolution",
]
