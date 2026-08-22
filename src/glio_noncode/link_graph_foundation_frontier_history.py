"""Immutable history for the C01-C04 fixture and assurance surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_public_data import LINK_GRAPH_FOUNDATION_FRONTIER_FIXTURE_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierHistoryEntry:
    revision_id: str
    fixture_version: str
    change_kind: str
    modules: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierHistory:
    entries: tuple[LinkGraphFoundationFrontierHistoryEntry, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def latest(self) -> LinkGraphFoundationFrontierHistoryEntry:
        return self.entries[-1]

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_history() -> LinkGraphFoundationFrontierHistory:
    entries = (LinkGraphFoundationFrontierHistoryEntry("d10-c01-c04-v1", LINK_GRAPH_FOUNDATION_FRONTIER_FIXTURE_VERSION, "initial", ("public_data", "adapters", "pipeline"), "initial aggregate baseline fixture"), LinkGraphFoundationFrontierHistoryEntry("d10-c01-c04-assurance", LINK_GRAPH_FOUNDATION_FRONTIER_FIXTURE_VERSION, "assurance", ("contracts", "lineage", "review", "release"), "source-to-release closure"))
    return LinkGraphFoundationFrontierHistory(entries)


__all__ = ["LinkGraphFoundationFrontierHistory", "LinkGraphFoundationFrontierHistoryEntry", "build_link_graph_foundation_frontier_history"]
