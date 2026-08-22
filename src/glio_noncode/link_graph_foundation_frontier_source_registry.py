"""Source receipt registry for the C01-C04 aggregate fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_public_data import LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY, LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierSource, default_link_graph_foundation_frontier_fixture
from .link_graph_foundation_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierSourceEntry:
    source: LinkGraphFoundationFrontierSource
    record_count: int
    operation_ids: tuple[str, ...]
    complete: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierSourceRegistry:
    entries: tuple[LinkGraphFoundationFrontierSourceEntry, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_id(self, source_id: str) -> LinkGraphFoundationFrontierSourceEntry:
        for item in self.entries:
            if item.source.source_id == source_id:
                return item
        raise KeyError(source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_source_registry(fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierSourceRegistry:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    entries = tuple(LinkGraphFoundationFrontierSourceEntry(source, sum(source.source_id in record.source_ids for record in value.records), tuple(sorted({record.operation.value for record in value.records if source.source_id in record.source_ids})), bool(source.uri and source.checksum and source.source_version and source.public_aggregate and source.context_key == LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY)) for source in value.sources)
    checks = (check("sources_present", bool(entries), "source receipts are present"), check("source_ids_unique", len({item.source.source_id for item in entries}) == len(entries), "source IDs are unique"), check("receipt_complete", all(item.complete for item in entries), "source receipts are complete"), check("record_closure", all(item.record_count > 0 for item in entries), "every source is used"))
    return LinkGraphFoundationFrontierSourceRegistry(entries, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphFoundationFrontierSourceEntry", "LinkGraphFoundationFrontierSourceRegistry", "build_link_graph_foundation_frontier_source_registry"]
