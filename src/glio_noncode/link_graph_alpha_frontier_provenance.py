"""Content-addressed provenance graph for link evidence and decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierProvenanceNode:
    node_id: str
    node_kind: str
    label: str
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierProvenanceEdge:
    edge_id: str
    parent_id: str
    child_id: str
    relation: str
    evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierProvenanceGraph:
    nodes: tuple[LinkGraphAlphaFrontierProvenanceNode, ...]
    edges: tuple[LinkGraphAlphaFrontierProvenanceEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def node(self, node_id: str) -> LinkGraphAlphaFrontierProvenanceNode:
        for item in self.nodes:
            if item.node_id == node_id:
                return item
        raise KeyError(node_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"nodes": [item.to_dict() for item in self.nodes], "edges": [item.to_dict() for item in self.edges], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_provenance(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierProvenanceGraph:
    source_nodes = [LinkGraphAlphaFrontierProvenanceNode(f"source:{item.source_id}", "source", item.source_id, item.context_key, item.checksum) for item in fixture.sources]
    record_nodes = [LinkGraphAlphaFrontierProvenanceNode(f"record:{row.record_id}", "record", row.record_id, fixture.context_key if row.record_id not in {item.record_id for item in fixture.records if item.context_key == fixture.foreign_context_key} else fixture.foreign_context_key, row.adapter.content_address) for row in evaluation.rows]
    nodes = tuple(source_nodes + record_nodes)
    edges = []
    for row in evaluation.rows:
        record = next(item for item in fixture.records if item.record_id == row.record_id)
        for source_id in record.source_ids:
            edges.append(LinkGraphAlphaFrontierProvenanceEdge(content_hash((source_id, row.record_id)), f"source:{source_id}", f"record:{row.record_id}", "supports", row.adapter.evidence_ids))
    values = tuple(edges)
    accepted = bool(nodes) and len({item.node_id for item in nodes}) == len(nodes) and all(item.parent_id in {node.node_id for node in nodes} and item.child_id in {node.node_id for node in nodes} for item in values)
    return LinkGraphAlphaFrontierProvenanceGraph(nodes, values, accepted)


__all__ = ["LinkGraphAlphaFrontierProvenanceEdge", "LinkGraphAlphaFrontierProvenanceGraph", "LinkGraphAlphaFrontierProvenanceNode", "build_link_graph_alpha_frontier_provenance"]
