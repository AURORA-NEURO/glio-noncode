"""Small immutable history record for fixture and release revisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_public_data import LINK_GRAPH_ALPHA_FRONTIER_FIXTURE_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierHistoryEntry:
    revision_id: str
    fixture_version: str
    change_kind: str
    changed_modules: tuple[str, ...]
    compatibility: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierHistory:
    entries: tuple[LinkGraphAlphaFrontierHistoryEntry, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def latest(self) -> LinkGraphAlphaFrontierHistoryEntry:
        return self.entries[-1]

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_history() -> LinkGraphAlphaFrontierHistory:
    entries = (LinkGraphAlphaFrontierHistoryEntry("d10-c09-c12-v1", LINK_GRAPH_ALPHA_FRONTIER_FIXTURE_VERSION, "initial", ("public_data", "adapters", "pipeline"), "new-surface", "initial aggregate fixture and bounded replay surface"), LinkGraphAlphaFrontierHistoryEntry("d10-c09-c12-v1-assurance", LINK_GRAPH_ALPHA_FRONTIER_FIXTURE_VERSION, "assurance", ("contracts", "lineage", "review", "release"), "compatible", "assurance modules close source-to-release traceability"))
    return LinkGraphAlphaFrontierHistory(entries)


__all__ = ["LinkGraphAlphaFrontierHistory", "LinkGraphAlphaFrontierHistoryEntry", "build_link_graph_alpha_frontier_history"]
