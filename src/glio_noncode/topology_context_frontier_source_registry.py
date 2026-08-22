"""Source closure and scope checks for the topology tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_public_data import TopologyContextFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierSourceEntry:
    source_id: str
    uri: str
    source_kind: str
    release: str
    record_count: int
    referenced: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierSourceRegistry:
    entries: tuple[TopologyContextFrontierSourceEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_source_registry(
    fixture: TopologyContextFrontierFixture,
) -> TopologyContextFrontierSourceRegistry:
    entries = tuple(
        TopologyContextFrontierSourceEntry(
            source.source_id,
            source.uri,
            source.source_kind,
            source.release,
            sum(source.source_id in record.source_ids for record in fixture.records),
            any(source.source_id in record.source_ids for record in fixture.records)
            or source.source_kind == "method_reference",
        )
        for source in fixture.sources
    )
    return TopologyContextFrontierSourceRegistry(entries, all(item.referenced for item in entries))


__all__ = [
    "TopologyContextFrontierSourceEntry",
    "TopologyContextFrontierSourceRegistry",
    "build_topology_context_frontier_source_registry",
]
