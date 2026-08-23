"""Source registry that makes public aggregate use and versions inspectable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_public_data import CohortFoundationFixture


@dataclass(frozen=True, slots=True)
class CohortFoundationSourceEntry:
    source_id: str
    title: str
    url: str
    version: str
    license: str
    permitted_use: str
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationSourceRegistry:
    registry_id: str
    entries: tuple[CohortFoundationSourceEntry, ...]
    closed: bool
    content_address: str

    def by_id(self, source_id: str) -> CohortFoundationSourceEntry:
        return next(item for item in self.entries if item.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_source_registry(fixture: CohortFoundationFixture) -> CohortFoundationSourceRegistry:
    entries = tuple(CohortFoundationSourceEntry(item.source_id, item.title, item.url, item.version, item.license, "aggregate research use", item.context_key, content_hash(item.to_dict())) for item in fixture.sources)
    declared = {item.source_id for item in entries}
    cited = {source_id for record in fixture.records for source_id in record.source_ids}
    body = {"registry_id": "cohort-foundation-frontier-sources", "entries": entries, "declared": declared, "cited": cited}
    return CohortFoundationSourceRegistry(body["registry_id"], entries, declared == cited, content_hash(body))


__all__ = ["CohortFoundationSourceEntry", "CohortFoundationSourceRegistry", "build_cohort_foundation_frontier_source_registry"]
