"""Source receipt registry and boundary checks for the link fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_public_data import (
    LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY,
    LinkGraphAlphaFrontierFixture,
    LinkGraphAlphaFrontierSource,
    default_link_graph_alpha_frontier_fixture,
)
from .link_graph_alpha_frontier_support import check, report
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierSourceEntry:
    source: LinkGraphAlphaFrontierSource
    record_count: int
    operation_ids: tuple[str, ...]
    receipt_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierSourceRegistry:
    entries: tuple[LinkGraphAlphaFrontierSourceEntry, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_id(self, source_id: str) -> LinkGraphAlphaFrontierSourceEntry:
        for item in self.entries:
            if item.source.source_id == source_id:
                return item
        raise KeyError(source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_source_registry(fixture: LinkGraphAlphaFrontierFixture | None = None) -> LinkGraphAlphaFrontierSourceRegistry:
    value = fixture or default_link_graph_alpha_frontier_fixture()
    by_source = {source.source_id: source for source in value.sources}
    entries = tuple(
        LinkGraphAlphaFrontierSourceEntry(
            source,
            sum(source.source_id in record.source_ids for record in value.records),
            tuple(sorted({record.operation.value for record in value.records if source.source_id in record.source_ids})),
            bool(source.uri and source.checksum and source.source_version and source.context_key == LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY and source.public_aggregate),
        )
        for source in value.sources
    )
    checks = (
        check("sources_present", bool(entries), "source registry is non-empty", evidence=by_source),
        check("sources_unique", len(by_source) == len(value.sources), "source identifiers are unique"),
        check("receipts_complete", all(item.receipt_complete for item in entries), "every receipt carries boundary fields"),
        check("records_resolved", all(set(record.source_ids) <= set(by_source) for record in value.records), "every record resolves to a receipt"),
        check("coverage_complete", all(item.record_count > 0 for item in entries), "every declared source is exercised"),
    )
    return LinkGraphAlphaFrontierSourceRegistry(entries, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierSourceEntry", "LinkGraphAlphaFrontierSourceRegistry", "build_link_graph_alpha_frontier_source_registry"]
