"""Fixture scope counters for context and boundary classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFixtureScope:
    exact_context_records: int
    foreign_context_records: int
    empty_records: int
    other_boundary_records: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def summarize_cohort_alpha_frontier_fixture_scope(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierFixtureScope:
    exact = sum(record.control_class == "positive" or record.control_class == "incomplete_control" or record.control_class == "contradictory_control" for record in fixture.records)
    foreign = sum(record.control_class == "foreign_context" for record in fixture.records)
    empty = sum(record.control_class == "empty_control" for record in fixture.records)
    other = len(fixture.records) - exact - foreign - empty
    body = {"exact": exact, "foreign": foreign, "empty": empty, "other": other}
    return CohortAlphaFrontierFixtureScope(exact, foreign, empty, other, sum(body.values()) == 16 and foreign == 4 and empty == 4, content_hash(body, prefix="alpha-fixture-scope"))


__all__ = ["CohortAlphaFrontierFixtureScope", "summarize_cohort_alpha_frontier_fixture_scope"]
