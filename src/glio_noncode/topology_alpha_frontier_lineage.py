"""Record-to-source lineage closure for topology-alpha results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierLineageEntry:
    record_id: str
    operation: str
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    state: str
    record_address: str
    result_address: str
    closed: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierLineage:
    entries: tuple[TopologyAlphaFrontierLineageEntry, ...]
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> TopologyAlphaFrontierLineageEntry:
        for item in self.entries:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "source_ids": self.source_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_lineage(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierLineage:
    known = {item.source_id for item in fixture.sources}
    entries = tuple(TopologyAlphaFrontierLineageEntry(row.record_id, row.operation, row.adapter.source_ids, row.adapter.evidence_ids, row.observed_state, fixture.records[index].content_address, row.adapter.content_address, bool(row.adapter.source_ids) and set(row.adapter.source_ids) <= known and bool(row.adapter.content_address)) for index, row in enumerate(evaluation.rows))
    return TopologyAlphaFrontierLineage(entries, tuple(sorted(known)), len(entries) == len(fixture.records) and all(item.closed for item in entries))


__all__ = ["TopologyAlphaFrontierLineage", "TopologyAlphaFrontierLineageEntry", "build_topology_alpha_frontier_lineage"]
