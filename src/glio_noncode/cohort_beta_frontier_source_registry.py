"""Closed registry of public source receipts used by C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture, CohortBetaFrontierSource
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSourceRegistry:
    sources: tuple[CohortBetaFrontierSource, ...]
    closed: bool
    content_address: str

    def by_id(self, source_id: str) -> CohortBetaFrontierSource:
        return next(item for item in self.sources if item.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_source_registry(fixture: CohortBetaFrontierFixture) -> CohortBetaFrontierSourceRegistry:
    values = tuple(sorted(fixture.sources, key=lambda item: item.source_id))
    referenced = {source_id for record in fixture.records for source_id in record.source_ids}
    closed = bool(values) and referenced <= {item.source_id for item in values} and all(item.url.startswith("https://") for item in values)
    return CohortBetaFrontierSourceRegistry(values, closed, content_hash({"sources": values, "closed": closed}, prefix="source-registry"))


__all__ = ["CohortBetaFrontierSourceRegistry", "build_cohort_beta_frontier_source_registry"]
