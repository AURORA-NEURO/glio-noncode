"""Content-addressed provenance graph for C05-C08 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierProvenanceNode:
    node_id: str
    node_kind: str
    content_address: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierProvenanceEdge:
    parent_id: str
    child_id: str
    edge_kind: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierProvenanceGraph:
    fixture_id: str
    nodes: tuple[CausalBetaFrontierProvenanceNode, ...]
    edges: tuple[CausalBetaFrontierProvenanceEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(item.node_id for item in self.nodes)

    @property
    def orphan_node_ids(self) -> tuple[str, ...]:
        referenced = {item.parent_id for item in self.edges} | {item.child_id for item in self.edges}
        return tuple(item for item in self.node_ids if item not in referenced)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "nodes": [item.to_dict() for item in self.nodes], "edges": [item.to_dict() for item in self.edges], "node_count": len(self.nodes), "edge_count": len(self.edges), "orphan_node_ids": self.orphan_node_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_provenance(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation) -> CausalBetaFrontierProvenanceGraph:
    nodes: list[CausalBetaFrontierProvenanceNode] = []
    edges: list[CausalBetaFrontierProvenanceEdge] = []
    for source in fixture.sources:
        nodes.append(CausalBetaFrontierProvenanceNode(f"source:{source.source_id}", "source", source.content_address, source.title))
    nodes.append(CausalBetaFrontierProvenanceNode(f"fixture:{fixture.fixture_id}", "fixture", fixture.content_address, fixture.fixture_id))
    for record in fixture.records:
        record_node = f"record:{record.record_id}"
        nodes.append(CausalBetaFrontierProvenanceNode(record_node, "record", record.content_address, record.record_id))
        edges.append(CausalBetaFrontierProvenanceEdge(f"fixture:{fixture.fixture_id}", record_node, "fixture_to_record"))
        edges.extend(CausalBetaFrontierProvenanceEdge(f"source:{source_id}", record_node, "source_to_record") for source_id in record.source_ids)
    for row in evaluation.rows:
        result_node = f"result:{row.adapter.content_address}"
        nodes.append(CausalBetaFrontierProvenanceNode(result_node, "result", row.adapter.content_address, row.record_id))
        edges.append(CausalBetaFrontierProvenanceEdge(f"record:{row.record_id}", result_node, "record_to_result"))
    values = tuple(nodes)
    node_ids = {item.node_id for item in values}
    referenced = {item.parent_id for item in edges} | {item.child_id for item in edges}
    accepted = bool(values) and len(node_ids) == len(values) and referenced <= node_ids and not (set(node_ids) - referenced)
    return CausalBetaFrontierProvenanceGraph(fixture.fixture_id, values, tuple(edges), accepted)


__all__ = ["CausalBetaFrontierProvenanceEdge", "CausalBetaFrontierProvenanceGraph", "CausalBetaFrontierProvenanceNode", "build_causal_beta_frontier_provenance"]
