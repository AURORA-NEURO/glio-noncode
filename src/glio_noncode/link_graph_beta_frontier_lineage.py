"""Record-to-source-to-replay lineage for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierLineageEdge:
    edge_id: str
    from_id: str
    to_id: str
    edge_type: str
    record_id: str
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierLineage:
    fixture_id: str
    edges: tuple[LinkGraphBetaFrontierLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def record_edges(self) -> tuple[LinkGraphBetaFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.edge_type == "record_to_result")

    def for_record(self, record_id: str) -> tuple[LinkGraphBetaFrontierLineageEdge, ...]:
        return tuple(item for item in self.edges if item.record_id == record_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "edges": [item.to_dict() for item in self.edges], "edge_count": len(self.edges), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_lineage(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierLineage:
    edges = []
    source_map = {source.source_id: source for source in fixture.sources}
    for record, row in zip(fixture.records, evaluation.rows):
        for source_id in record.source_ids:
            source = source_map[source_id]
            edges.append(LinkGraphBetaFrontierLineageEdge(f"{record.record_id}:source:{source_id}", f"record:{record.record_id}", f"source:{source_id}", "source_to_record", record.record_id, (source_id,), source.checksum))
        edges.append(LinkGraphBetaFrontierLineageEdge(f"{record.record_id}:result", f"record:{record.record_id}", f"result:{record.record_id}", "record_to_result", record.record_id, record.source_ids, row.adapter.content_address))
    values = tuple(edges)
    return LinkGraphBetaFrontierLineage(fixture.fixture_id, values, bool(values) and len([edge for edge in values if edge.edge_type == "record_to_result"]) == len(fixture.records) and all(edge.content_address.startswith("sha256:") for edge in values))


def verify_link_graph_beta_frontier_lineage(lineage: LinkGraphBetaFrontierLineage, fixture: LinkGraphBetaFrontierFixture) -> bool:
    return lineage.accepted and len(lineage.record_edges) == len(fixture.records) and all(lineage.for_record(record.record_id) for record in fixture.records)


__all__ = ["LinkGraphBetaFrontierLineage", "LinkGraphBetaFrontierLineageEdge", "build_link_graph_beta_frontier_lineage", "verify_link_graph_beta_frontier_lineage"]
