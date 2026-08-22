"""Version history record for the beta frontier fixture and contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_public_data import LINK_GRAPH_BETA_FRONTIER_FIXTURE_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierHistoryEntry:
    version: str
    date: str
    change: str
    boundary: str
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierHistory:
    entries: tuple[LinkGraphBetaFrontierHistoryEntry, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_history() -> LinkGraphBetaFrontierHistory:
    entries = (LinkGraphBetaFrontierHistoryEntry(LINK_GRAPH_BETA_FRONTIER_FIXTURE_VERSION, "2026-08-22", "opened C05-C08 public aggregate fixture and typed replay", "public_aggregate_non_patient", True), LinkGraphBetaFrontierHistoryEntry("2026.08.beta-contracts.v1", "2026-08-22", "locked operation contracts and control outcomes", "public_aggregate_non_patient", True))
    return LinkGraphBetaFrontierHistory(entries)


__all__ = ["LinkGraphBetaFrontierHistory", "LinkGraphBetaFrontierHistoryEntry", "build_link_graph_beta_frontier_history"]
