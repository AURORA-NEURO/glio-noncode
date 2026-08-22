"""Source receipt closure for topology-alpha aggregate operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, TopologyAlphaFrontierSource, default_topology_alpha_frontier_fixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierSourceEntry:
    source_id: str
    source_kind: str
    source_version: str
    uri: str
    checksum: str
    context_key: str
    public_aggregate: bool
    record_count: int
    receipt_state: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"source_id": self.source_id, "source_kind": self.source_kind, "source_version": self.source_version, "uri": self.uri, "checksum": self.checksum, "context_key": self.context_key, "public_aggregate": self.public_aggregate, "record_count": self.record_count, "receipt_state": self.receipt_state}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierSourceRegistry:
    entries: tuple[TopologyAlphaFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_source(self, source_id: str) -> TopologyAlphaFrontierSourceEntry:
        for item in self.entries:
            if item.source_id == source_id:
                return item
        raise KeyError(source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_source_registry(fixture: TopologyAlphaFrontierFixture | None = None) -> TopologyAlphaFrontierSourceRegistry:
    value = fixture or default_topology_alpha_frontier_fixture()
    entries = tuple(TopologyAlphaFrontierSourceEntry(source.source_id, source.source_kind, source.source_version, source.uri, source.checksum, source.context_key, source.public_aggregate, sum(source.source_id in row.source_ids for row in value.records), "received") for source in value.sources)
    return TopologyAlphaFrontierSourceRegistry(entries, len(entries) == 4 and all(item.record_count > 0 and item.public_aggregate and item.checksum.startswith("sha256:") for item in entries))


__all__ = ["TopologyAlphaFrontierSourceEntry", "TopologyAlphaFrontierSourceRegistry", "build_topology_alpha_frontier_source_registry"]
