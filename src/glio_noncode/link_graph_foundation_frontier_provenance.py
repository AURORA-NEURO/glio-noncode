"""Content-addressed source and record provenance graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProvenanceNode:
    node_id: str
    node_kind: str
    label: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProvenanceEdge:
    edge_id: str
    parent_id: str
    child_id: str
    relation: str
    evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierProvenanceGraph:
    nodes: tuple[LinkGraphFoundationFrontierProvenanceNode, ...]
    edges: tuple[LinkGraphFoundationFrontierProvenanceEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"nodes": [item.to_dict() for item in self.nodes], "edges": [item.to_dict() for item in self.edges], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_provenance(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> LinkGraphFoundationFrontierProvenanceGraph:
    nodes = tuple(LinkGraphFoundationFrontierProvenanceNode(f"source:{item.source_id}", "source", item.source_id, item.checksum) for item in fixture.sources) + tuple(LinkGraphFoundationFrontierProvenanceNode(f"record:{row.record_id}", "record", row.record_id, row.adapter.content_address) for row in evaluation.rows)
    edges = tuple(LinkGraphFoundationFrontierProvenanceEdge(content_hash((source, row.record_id)), f"source:{source}", f"record:{row.record_id}", "supports", row.adapter.evidence_ids) for row in evaluation.rows for source in next(item for item in fixture.records if item.record_id == row.record_id).source_ids)
    return LinkGraphFoundationFrontierProvenanceGraph(nodes, edges, len(nodes) == 21 and len(edges) >= 16)


__all__ = ["LinkGraphFoundationFrontierProvenanceEdge", "LinkGraphFoundationFrontierProvenanceGraph", "LinkGraphFoundationFrontierProvenanceNode", "build_link_graph_foundation_frontier_provenance"]
