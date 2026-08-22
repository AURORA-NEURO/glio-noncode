"""Source receipt closure for the public topology-beta fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_public_data import (
    TopologyBetaFrontierFixture,
    TopologyBetaFrontierSource,
    default_topology_beta_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierSourceEntry:
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
class TopologyBetaFrontierSourceRegistry:
    entries: tuple[TopologyBetaFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_source(self, source_id: str) -> TopologyBetaFrontierSourceEntry:
        for item in self.entries:
            if item.source_id == source_id:
                return item
        raise KeyError(source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _entry(source: TopologyBetaFrontierSource, record_count: int) -> TopologyBetaFrontierSourceEntry:
    return TopologyBetaFrontierSourceEntry(source.source_id, source.source_kind, source.source_version, source.uri, source.checksum, source.context_key, source.public_aggregate, record_count, "received")


def build_topology_beta_frontier_source_registry(fixture: TopologyBetaFrontierFixture | None = None) -> TopologyBetaFrontierSourceRegistry:
    value = fixture or default_topology_beta_frontier_fixture()
    entries = tuple(_entry(source, sum(source.source_id in row.source_ids for row in value.records)) for source in value.sources)
    accepted = len(entries) == 4 and all(item.record_count > 0 and item.public_aggregate and item.receipt_state == "received" and item.checksum.startswith("sha256:") for item in entries)
    return TopologyBetaFrontierSourceRegistry(entries, accepted)


__all__ = ["TopologyBetaFrontierSourceEntry", "TopologyBetaFrontierSourceRegistry", "build_topology_beta_frontier_source_registry"]
