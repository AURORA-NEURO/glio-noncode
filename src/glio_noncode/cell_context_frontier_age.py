"""Depth checks for adult/pediatric context routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context import ContextResolution, ContextResolutionState
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierAgeRouteObservation:
    route: str
    evidence_count: int
    source_ids: tuple[str, ...]
    agrees_with_declaration: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.route not in {"adult", "pediatric", "unknown"} or self.evidence_count < 0:
            raise ValidationError("age route observation is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierAgeDepthReport:
    context_key: str
    declared_route: str
    resolved_route: str | None
    state: str
    observations: tuple[CellContextFrontierAgeRouteObservation, ...]
    conflict: bool
    unknown: bool
    review_required: bool
    limitations: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.context_key or self.declared_route not in {"adult", "pediatric", "unknown"}:
            raise ValidationError("age depth report is invalid")
        if not self.limitations:
            raise ValidationError("age depth report needs limitations")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def profile_age_route_resolution(
    resolution: ContextResolution, *, declared_route: str
) -> CellContextFrontierAgeDepthReport:
    resolved = resolution.selected_candidate_id
    conflict = resolution.state is ContextResolutionState.CONTRADICTORY
    unknown = declared_route == "unknown" or resolution.state is ContextResolutionState.ABSTAINED
    observation = CellContextFrontierAgeRouteObservation(
        resolved or "unknown",
        len(resolution.evidence_ids),
        resolution.source_ids,
        bool(resolved) and resolved == declared_route,
    )
    review_required = (
        conflict
        or unknown
        or resolution.state
        in {ContextResolutionState.AMBIGUOUS, ContextResolutionState.OUT_OF_DOMAIN}
    )
    return CellContextFrontierAgeDepthReport(
        resolution.context_key,
        declared_route,
        resolved,
        resolution.state.value,
        (observation,),
        conflict,
        unknown,
        review_required,
        resolution.limitations
        + ("Age routing partitions evidence; it does not determine disease behavior.",),
        resolution.state is ContextResolutionState.SUPPORTED and not conflict,
    )


__all__ = [
    "CellContextFrontierAgeDepthReport",
    "CellContextFrontierAgeRouteObservation",
    "profile_age_route_resolution",
]
