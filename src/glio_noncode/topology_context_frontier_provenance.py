"""Provenance graph for the Domain 09 topology context package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import TopologyContextFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierProvenanceNode:
    node_id: str
    node_kind: str
    label: str
    content_address: str
    aggregate: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierProvenanceEdge:
    edge_id: str
    source_node: str
    target_node: str
    relation: str
    context_key: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierProvenanceGraph:
    nodes: tuple[TopologyContextFrontierProvenanceNode, ...]
    edges: tuple[TopologyContextFrontierProvenanceEdge, ...]
    accepted: bool
    source_count: int
    result_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(item.node_id for item in self.nodes)

    @property
    def edge_ids(self) -> tuple[str, ...]:
        return tuple(item.edge_id for item in self.edges)

    def nodes_by_kind(self, node_kind: str) -> tuple[TopologyContextFrontierProvenanceNode, ...]:
        return tuple(item for item in self.nodes if item.node_kind == node_kind)

    def edges_for_record(self, record_id: str) -> tuple[TopologyContextFrontierProvenanceEdge, ...]:
        return tuple(item for item in self.edges if item.target_node == f"result:{record_id}")

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "accepted": self.accepted,
            "source_count": self.source_count,
            "result_count": self.result_count,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_provenance(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierProvenanceGraph:
    source_nodes = tuple(
        TopologyContextFrontierProvenanceNode(
            f"source:{item.source_id}",
            "source",
            item.title,
            item.content_address,
            item.public_aggregate,
        )
        for item in fixture.sources
    )
    record_nodes = tuple(
        TopologyContextFrontierProvenanceNode(
            f"record:{item.record_id}",
            "record",
            item.description,
            item.content_address,
            True,
        )
        for item in fixture.records
    )
    result_nodes = tuple(
        TopologyContextFrontierProvenanceNode(
            f"result:{item.record_id}",
            "result",
            item.operation,
            item.adapter.content_address,
            True,
        )
        for item in evaluation.rows
    )
    edges = tuple(
        edge
        for record in fixture.records
        for edge in (
            TopologyContextFrontierProvenanceEdge(
                f"source-record:{record.record_id}:{source_id}",
                f"source:{source_id}",
                f"record:{record.record_id}",
                "source_to_record",
                record.context_key,
            )
            for source_id in record.source_ids
        )
    ) + tuple(
        TopologyContextFrontierProvenanceEdge(
            f"record-result:{item.record_id}",
            f"record:{item.record_id}",
            f"result:{item.record_id}",
            "record_to_result",
            fixture.context_key,
        )
        for item in evaluation.rows
    )
    nodes = source_nodes + record_nodes + result_nodes
    node_set = set(item.node_id for item in nodes)
    accepted = (
        len(source_nodes) == 4
        and len(record_nodes) == 16
        and len(result_nodes) == 16
        and len(edges) >= 32
        and all(item.source_node in node_set and item.target_node in node_set for item in edges)
        and all(item.aggregate for item in nodes)
    )
    return TopologyContextFrontierProvenanceGraph(
        nodes,
        edges,
        accepted,
        len(source_nodes),
        len(result_nodes),
    )


__all__ = [
    "TopologyContextFrontierProvenanceEdge",
    "TopologyContextFrontierProvenanceGraph",
    "TopologyContextFrontierProvenanceNode",
    "build_topology_context_frontier_provenance",
]
