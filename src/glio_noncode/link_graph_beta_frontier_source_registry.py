"""Source receipt registry for the C05-C08 public aggregate inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierSource, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierSourceRegistry:
    fixture_id: str
    sources: tuple[LinkGraphBetaFrontierSource, ...]
    record_source_coverage: dict[str, int]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def source(self, source_id: str) -> LinkGraphBetaFrontierSource:
        return next(item for item in self.sources if item.source_id == source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "sources": [item.to_dict() for item in self.sources], "record_source_coverage": self.record_source_coverage, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_source_registry(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierSourceRegistry:
    value = fixture or default_link_graph_beta_frontier_fixture()
    coverage = {source.source_id: sum(source.source_id in record.source_ids for record in value.records) for source in value.sources}
    source_ids = {source.source_id for source in value.sources}
    accepted = bool(value.sources) and all(source.public_aggregate and source.checksum.startswith("sha256:") for source in value.sources) and all(set(record.source_ids) <= source_ids for record in value.records)
    return LinkGraphBetaFrontierSourceRegistry(value.fixture_id, value.sources, coverage, accepted)


__all__ = ["LinkGraphBetaFrontierSourceRegistry", "build_link_graph_beta_frontier_source_registry"]
