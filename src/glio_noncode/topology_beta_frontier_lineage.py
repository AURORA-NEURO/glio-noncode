"""Record-to-source lineage closure for topology-beta outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierLineageEntry:
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
class TopologyBetaFrontierLineage:
    entries: tuple[TopologyBetaFrontierLineageEntry, ...]
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> TopologyBetaFrontierLineageEntry:
        for item in self.entries:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"entries": [item.to_dict() for item in self.entries], "source_ids": self.source_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_lineage(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierLineage:
    known = {item.source_id for item in fixture.sources}
    entries = tuple(TopologyBetaFrontierLineageEntry(item.record_id, item.operation, item.adapter.source_ids, item.adapter.evidence_ids, item.observed_state, fixture.records[index].content_address, item.adapter.content_address, bool(item.adapter.source_ids) and set(item.adapter.source_ids) <= known and bool(item.adapter.content_address)) for index, item in enumerate(evaluation.rows))
    accepted = len(entries) == len(fixture.records) and all(item.closed for item in entries)
    return TopologyBetaFrontierLineage(entries, tuple(sorted(known)), accepted)


__all__ = ["TopologyBetaFrontierLineage", "TopologyBetaFrontierLineageEntry", "build_topology_beta_frontier_lineage"]
