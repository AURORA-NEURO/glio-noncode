"""Faceted projections for operation, state, control, and disposition review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_controls import CausalAlphaFrontierControlCoverage
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierProjectionFacet:
    dimension: str
    value: str
    count: int
    record_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"dimension": self.dimension, "value": self.value, "count": self.count, "record_ids": self.record_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierProjectionReport:
    fixture_id: str
    facets: tuple[CausalAlphaFrontierProjectionFacet, ...]
    dimensions: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def facet(self, dimension: str, value: str) -> CausalAlphaFrontierProjectionFacet:
        return next(item for item in self.facets if item.dimension == dimension and item.value == value)

    def where(self, *, dimension: str | None = None, value: str | None = None) -> tuple[CausalAlphaFrontierProjectionFacet, ...]:
        return tuple(item for item in self.facets if (dimension is None or item.dimension == dimension) and (value is None or item.value == value))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "facets": [item.to_dict() for item in self.facets], "dimensions": self.dimensions, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_projections(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, controls: CausalAlphaFrontierControlCoverage, decisions: tuple[CausalAlphaFrontierDecision, ...]) -> CausalAlphaFrontierProjectionReport:
    records = fixture.record_map()
    decision_map = {item.record_id: item for item in decisions}
    control_map = {item.record_id: item.control_class.value for item in controls.rows}
    groups: dict[tuple[str, str], list[str]] = {}
    for result in evaluation.evaluation.results:
        record = records[result.record_id]
        decision = decision_map[result.record_id]
        dimensions = (
            ("operation", result.operation.value),
            ("state", result.observed_state.value),
            ("role", record.role.value),
            ("context", "foreign" if record.context_key == fixture.foreign_context_key else "exact"),
            ("disposition", decision.disposition.value),
            ("control_class", control_map[result.record_id]),
        )
        for dimension, value in dimensions:
            groups.setdefault((dimension, value), []).append(result.record_id)
    facets = tuple(CausalAlphaFrontierProjectionFacet(dimension, value, len(ids), tuple(sorted(ids)), True) for (dimension, value), ids in sorted(groups.items()))
    return CausalAlphaFrontierProjectionReport(fixture.fixture_id, facets, tuple(sorted({item.dimension for item in facets})), len(facets) >= 20 and all(item.accepted for item in facets))


__all__ = ["CausalAlphaFrontierProjectionFacet", "CausalAlphaFrontierProjectionReport", "build_causal_alpha_frontier_projections"]
