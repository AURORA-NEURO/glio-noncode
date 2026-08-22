"""Content-addressed provenance graph for beta evidence and replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierProvenanceNode:
    node_id: str
    node_type: str
    address: str
    record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierProvenanceGraph:
    fixture_id: str
    nodes: tuple[LinkGraphBetaFrontierProvenanceNode, ...]
    edges: tuple[tuple[str, str], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def nodes_of_type(self, node_type: str) -> tuple[LinkGraphBetaFrontierProvenanceNode, ...]:
        return tuple(item for item in self.nodes if item.node_type == node_type)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "nodes": [item.to_dict() for item in self.nodes], "edges": self.edges, "node_count": len(self.nodes), "edge_count": len(self.edges), "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_provenance(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierProvenanceGraph:
    nodes = [LinkGraphBetaFrontierProvenanceNode(f"source:{source.source_id}", "source", source.checksum) for source in fixture.sources]
    nodes.extend(LinkGraphBetaFrontierProvenanceNode(f"record:{record.record_id}", "record", record.content_address, record.record_id) for record in fixture.records)
    nodes.extend(LinkGraphBetaFrontierProvenanceNode(f"result:{row.record_id}", "result", row.adapter.content_address, row.record_id) for row in evaluation.rows)
    edges = [(f"source:{source_id}", f"record:{record.record_id}") for record in fixture.records for source_id in record.source_ids]
    edges.extend((f"record:{row.record_id}", f"result:{row.record_id}") for row in evaluation.rows)
    values = tuple(nodes)
    return LinkGraphBetaFrontierProvenanceGraph(fixture.fixture_id, values, tuple(edges), bool(values) and len(values) == len(fixture.sources) + len(fixture.records) + len(evaluation.rows) and evaluation.accepted)


__all__ = ["LinkGraphBetaFrontierProvenanceGraph", "LinkGraphBetaFrontierProvenanceNode", "build_link_graph_beta_frontier_provenance"]
