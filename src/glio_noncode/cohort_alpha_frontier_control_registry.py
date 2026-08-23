"""Named control registry for positive, incomplete, foreign, and empty paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierControlDefinition:
    control_class: str
    expected_operation_count: int
    expected_state: str
    purpose: str
    exclusion_rule: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierControlRegistry:
    definitions: tuple[CohortAlphaFrontierControlDefinition, ...]
    observed_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_control_registry(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierControlRegistry:
    raw = (
        ("positive", "supported", "publication path", "retain only exact-context evidence"),
        ("incomplete_control", "partial", "missing-channel control", "hold until required channel is receipted"),
        ("contradictory_control", "ambiguous", "direction disagreement control", "hold until cohort direction is resolved"),
        ("foreign_context", "out_of_domain", "context control", "quarantine foreign context"),
        ("empty_control", "abstained", "empty observation control", "retain abstention"),
    )
    observed = {control_class: sum(record.control_class == control_class for record in fixture.records) for control_class, _, _, _ in raw}
    definitions = tuple(
        CohortAlphaFrontierControlDefinition(
            control_class,
            observed.get(control_class, 0),
            state,
            purpose,
            exclusion,
            content_hash({"control_class": control_class, "count": observed.get(control_class, 0), "state": state, "purpose": purpose, "exclusion": exclusion}, prefix="alpha-control"),
        )
        for control_class, state, purpose, exclusion in raw
    )
    return CohortAlphaFrontierControlRegistry(
        definitions,
        observed,
        len(definitions) == 5 and sum(observed.values()) == 16 and all(item.expected_operation_count >= 1 for item in definitions),
        content_hash({"definitions": definitions, "observed": observed}, prefix="alpha-control-registry"),
    )


__all__ = ["CohortAlphaFrontierControlDefinition", "CohortAlphaFrontierControlRegistry", "build_cohort_alpha_frontier_control_registry"]
