"""Fixture manifest with record ranges and expected control composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFixtureManifest:
    fixture_id: str
    version: str
    operation_ranges: dict[str, tuple[str, ...]]
    record_count: int
    source_count: int
    exact_context: str
    foreign_context: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_fixture_manifest(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierFixtureManifest:
    ranges = {operation: tuple(record.record_id for record in fixture.records if record.operation == operation) for operation in fixture.operations}
    body = {"fixture": fixture.fixture_id, "version": fixture.fixture_version, "ranges": ranges, "records": len(fixture.records), "sources": len(fixture.sources), "exact": fixture.context_key, "foreign": fixture.foreign_context_key}
    return CohortAlphaFrontierFixtureManifest(fixture.fixture_id, fixture.fixture_version, ranges, len(fixture.records), len(fixture.sources), fixture.context_key, fixture.foreign_context_key, len(ranges) == 4 and all(len(ids) == 4 for ids in ranges.values()), content_hash(body, prefix="alpha-fixture-manifest"))


__all__ = ["CohortAlphaFrontierFixtureManifest", "build_cohort_alpha_frontier_fixture_manifest"]
