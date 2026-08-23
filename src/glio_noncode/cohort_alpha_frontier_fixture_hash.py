"""Fixture hash receipt independent from serialized report objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFixtureHash:
    fixture_id: str
    record_addresses: tuple[str, ...]
    source_addresses: tuple[str, ...]
    aggregate_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_fixture_hash(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierFixtureHash:
    records = tuple(record.content_address for record in fixture.records)
    sources = tuple(source.content_address for source in fixture.sources)
    aggregate = content_hash({"fixture": fixture.fixture_id, "records": records, "sources": sources, "context": fixture.context_key, "version": fixture.fixture_version}, prefix="alpha-fixture-aggregate")
    return CohortAlphaFrontierFixtureHash(fixture.fixture_id, records, sources, aggregate, len(records) == 16 and len(sources) == 6 and bool(aggregate), content_hash({"fixture": fixture.fixture_id, "aggregate": aggregate}, prefix="alpha-fixture-hash"))


__all__ = ["CohortAlphaFrontierFixtureHash", "build_cohort_alpha_frontier_fixture_hash"]
