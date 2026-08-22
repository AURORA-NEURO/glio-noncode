"""Record-to-source-to-result lineage for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierLineageEdge:
    edge_id: str
    record_id: str
    source_id: str
    operation: str
    result_address: str
    evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierLineage:
    edges: tuple[LinkGraphFoundationFrontierLineageEdge, ...]
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> tuple[LinkGraphFoundationFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"edges": [item.to_dict() for item in self.edges], "record_ids": self.record_ids, "source_ids": self.source_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_lineage(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierLineage:
    source_map = {record.record_id: record for record in fixture.records}
    edges = tuple(LinkGraphFoundationFrontierLineageEdge(content_hash((row.record_id, source, row.adapter.content_address)), row.record_id, source, row.operation, row.adapter.content_address, row.adapter.evidence_ids) for row in evaluation.rows for source in source_map[row.record_id].source_ids)
    return LinkGraphFoundationFrontierLineage(edges, tuple(sorted({item.record_id for item in edges})), tuple(sorted({item.source_id for item in edges})), len({item.record_id for item in edges}) == len(fixture.records))


def verify_link_graph_foundation_frontier_lineage(lineage: LinkGraphFoundationFrontierLineage, fixture: LinkGraphFoundationFrontierFixture) -> bool:
    return lineage.accepted and set(lineage.record_ids) == {item.record_id for item in fixture.records} and set(lineage.source_ids) == {item.source_id for item in fixture.sources}


__all__ = ["LinkGraphFoundationFrontierLineage", "LinkGraphFoundationFrontierLineageEdge", "build_link_graph_foundation_frontier_lineage", "verify_link_graph_foundation_frontier_lineage"]
