"""Provenance graph for aggregate source, record, and result nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierProvenanceNode:
    node_id: str
    kind: str
    record_id: str | None
    source_id: str | None
    content_address: str
    aggregate: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierProvenanceEdge:
    from_node: str
    to_node: str
    relation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierProvenanceGraph:
    nodes: tuple[TopologyAlphaFrontierProvenanceNode, ...]
    edges: tuple[TopologyAlphaFrontierProvenanceEdge, ...]
    source_count: int
    record_count: int
    result_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def nodes_by_kind(self, kind: str) -> tuple[TopologyAlphaFrontierProvenanceNode, ...]:
        return tuple(item for item in self.nodes if item.kind == kind)

    def edges_for_record(self, record_id: str) -> tuple[TopologyAlphaFrontierProvenanceEdge, ...]:
        ids = {item.node_id for item in self.nodes if item.record_id == record_id}
        return tuple(item for item in self.edges if item.from_node in ids or item.to_node in ids)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"nodes": [item.to_dict() for item in self.nodes], "edges": [item.to_dict() for item in self.edges], "source_count": self.source_count, "record_count": self.record_count, "result_count": self.result_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_provenance(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierProvenanceGraph:
    nodes: list[TopologyAlphaFrontierProvenanceNode] = []
    edges: list[TopologyAlphaFrontierProvenanceEdge] = []
    for source in fixture.sources:
        nodes.append(TopologyAlphaFrontierProvenanceNode(f"source:{source.source_id}", "source", None, source.source_id, source.checksum, True, {"kind": source.source_kind, "version": source.source_version, "uri": source.uri}))
    for row in evaluation.rows:
        record_node, result_node = f"record:{row.record_id}", f"result:{row.record_id}"
        nodes.extend((TopologyAlphaFrontierProvenanceNode(record_node, "record", row.record_id, None, row.adapter.content_address, True, {"operation": row.operation, "role": row.role}), TopologyAlphaFrontierProvenanceNode(result_node, "result", row.record_id, None, row.adapter.content_address, True, {"state": row.observed_state, "issues": row.observed_issue_codes})))
        for source_id in row.adapter.source_ids:
            edges.append(TopologyAlphaFrontierProvenanceEdge(f"source:{source_id}", record_node, "supplies"))
        edges.append(TopologyAlphaFrontierProvenanceEdge(record_node, result_node, "evaluates"))
    return TopologyAlphaFrontierProvenanceGraph(tuple(nodes), tuple(edges), 4, len(evaluation.rows), len(evaluation.rows), len(nodes) == 4 + len(evaluation.rows) * 2 and len(edges) >= len(evaluation.rows) * 2 and all(item.aggregate for item in nodes))


__all__ = ["TopologyAlphaFrontierProvenanceEdge", "TopologyAlphaFrontierProvenanceGraph", "TopologyAlphaFrontierProvenanceNode", "build_topology_alpha_frontier_provenance"]
