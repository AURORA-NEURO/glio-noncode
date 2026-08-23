"""Descriptive fixture statistics separate from scientific inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFixtureStatistics:
    record_count: int
    source_count: int
    operation_count: int
    positive_count: int
    boundary_count: int
    average_sources_per_record: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def describe_cohort_alpha_frontier_fixture(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierFixtureStatistics:
    record_count = len(fixture.records)
    source_count = len(fixture.sources)
    positive = sum(record.control_class == "positive" for record in fixture.records)
    body = {"records": record_count, "sources": source_count, "operations": len(fixture.operations), "positive": positive, "boundary": record_count - positive, "average_sources": round(sum(len(record.source_ids) for record in fixture.records) / max(1, record_count), 4)}
    return CohortAlphaFrontierFixtureStatistics(record_count, source_count, len(fixture.operations), positive, record_count - positive, body["average_sources"], record_count == 16 and source_count == 6 and positive == 4, content_hash(body, prefix="alpha-fixture-statistics"))


__all__ = ["CohortAlphaFrontierFixtureStatistics", "describe_cohort_alpha_frontier_fixture"]
