"""Release history records for the public beta package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierHistoryEntry:
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
class TopologyBetaFrontierHistory:
    entries: tuple[TopologyBetaFrontierHistoryEntry, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def latest(self) -> TopologyBetaFrontierHistoryEntry:
        if not self.entries:
            raise LookupError("history is empty")
        return self.entries[-1]

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_history() -> TopologyBetaFrontierHistory:
    entries = (
        TopologyBetaFrontierHistoryEntry("topology-beta-frontier-bootstrap", "2026.08.d09-c05-c08.v0", "topology-beta-frontier-fixture", "superseded", 0, 0, 0, ("Initial contract boundary recorded.",), None),
        TopologyBetaFrontierHistoryEntry("topology-beta-frontier-release", "2026.08.d09-c05-c08.v1", "topology-beta-frontier-fixture", "accepted", 16, 4, 12, ("Four beta operations replayed.", "Controls remain visible.", "Aggregate scope is explicit."), "topology-beta-frontier-bootstrap"),
    )
    return TopologyBetaFrontierHistory(entries, len(entries) == 2 and entries[-1].status == "accepted" and entries[-1].predecessor == entries[-2].release_id)


__all__ = ["TopologyBetaFrontierHistory", "TopologyBetaFrontierHistoryEntry", "build_topology_beta_frontier_history"]
