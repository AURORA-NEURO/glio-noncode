"""Closed public source registry for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture, CohortAlphaFrontierSource
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceRegistry:
    sources: tuple[CohortAlphaFrontierSource, ...]
    closed: bool
    content_address: str

    def by_id(self, source_id: str) -> CohortAlphaFrontierSource:
        return next(item for item in self.sources if item.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_source_registry(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierSourceRegistry:
    values = tuple(sorted(fixture.sources, key=lambda item: item.source_id))
    referenced = {source_id for record in fixture.records for source_id in record.source_ids}
    closed = len(values) == 6 and referenced <= {item.source_id for item in values} and all(item.url.startswith("https://") for item in values)
    return CohortAlphaFrontierSourceRegistry(values, closed, content_hash({"sources": values, "closed": closed}, prefix="alpha-source-registry"))


__all__ = ["CohortAlphaFrontierSourceRegistry", "build_cohort_alpha_frontier_source_registry"]
