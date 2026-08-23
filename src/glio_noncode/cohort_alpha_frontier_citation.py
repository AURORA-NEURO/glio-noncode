"""Citation rows that keep public source references adjacent to results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCitation:
    citation_id: str
    record_id: str
    operation: str
    source_id: str
    source_label: str
    source_url: str
    version: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierCitationIndex:
    citations: tuple[CohortAlphaFrontierCitation, ...]
    source_count: int
    record_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_citations(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierCitationIndex:
    sources = {source.source_id: source for source in fixture.sources}
    citations = []
    for record in fixture.records:
        for source_id in record.source_ids:
            source = sources[source_id]
            body = {
                "record_id": record.record_id,
                "operation": record.operation,
                "source_id": source.source_id,
                "source_url": source.url,
                "version": source.version,
            }
            citations.append(
                CohortAlphaFrontierCitation(
                    f"citation-{record.record_id}-{source_id}",
                    record.record_id,
                    record.operation,
                    source.source_id,
                    source.label,
                    source.url,
                    source.version,
                    content_hash(body, prefix="alpha-citation"),
                )
            )
    values = tuple(citations)
    return CohortAlphaFrontierCitationIndex(
        values,
        len(sources),
        len({item.record_id for item in values}),
        len(sources) == 6 and len({item.record_id for item in values}) == 16 and all(item.source_url.startswith("https://") for item in values),
        content_hash(values, prefix="alpha-citation-index"),
    )


__all__ = ["CohortAlphaFrontierCitation", "CohortAlphaFrontierCitationIndex", "build_cohort_alpha_frontier_citations"]
