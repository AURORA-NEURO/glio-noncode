"""Release history for the public alpha package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierHistoryEntry:
    release_id: str
    version: str
    fixture_id: str
    status: str
    record_count: int
    source_count: int
    review_count: int
    notes: tuple[str, ...]
    predecessor: str | None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"release_id": self.release_id, "version": self.version, "fixture_id": self.fixture_id, "status": self.status, "record_count": self.record_count, "source_count": self.source_count, "review_count": self.review_count, "notes": self.notes, "predecessor": self.predecessor}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierHistory:
    entries: tuple[TopologyAlphaFrontierHistoryEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def latest(self) -> TopologyAlphaFrontierHistoryEntry:
        if not self.entries:
            raise LookupError("history is empty")
        return self.entries[-1]

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_history() -> TopologyAlphaFrontierHistory:
    entries = (TopologyAlphaFrontierHistoryEntry("topology-alpha-frontier-bootstrap", "2026.08.d09-c09-c12.v0", "topology-alpha-frontier-fixture", "superseded", 0, 0, 0, ("Initial operation contract boundary recorded.",), None), TopologyAlphaFrontierHistoryEntry("topology-alpha-frontier-release", "2026.08.d09-c09-c12.v1", "topology-alpha-frontier-fixture", "accepted", 16, 4, 12, ("Four alpha operations replayed.", "Controls and descriptive limits remain visible.", "Aggregate source scope is explicit."), "topology-alpha-frontier-bootstrap"))
    return TopologyAlphaFrontierHistory(entries, len(entries) == 2 and entries[-1].status == "accepted" and entries[-1].predecessor == entries[-2].release_id)


__all__ = ["TopologyAlphaFrontierHistory", "TopologyAlphaFrontierHistoryEntry", "build_topology_alpha_frontier_history"]
