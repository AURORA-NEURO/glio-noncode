"""Source-to-record-to-result lineage for the alpha frontier fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierLineageNode:
    node_id: str
    node_kind: str
    content_address: str
    source_ids: tuple[str, ...] = ()
    record_id: str | None = None
    parent_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "node_kind": self.node_kind, "content_address": self.content_address, "source_ids": self.source_ids, "record_id": self.record_id, "parent_ids": self.parent_ids}


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierLineage:
    fixture_id: str
    nodes: tuple[CausalAlphaFrontierLineageNode, ...]
    edges: tuple[tuple[str, str, str], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def node(self, node_id: str) -> CausalAlphaFrontierLineageNode:
        return next(item for item in self.nodes if item.node_id == node_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "nodes": [item.to_dict() for item in self.nodes], "edges": self.edges, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_lineage(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation) -> CausalAlphaFrontierLineage:
    nodes: list[CausalAlphaFrontierLineageNode] = []
    edges: list[tuple[str, str, str]] = []
    source_nodes: dict[str, str] = {}
    for source in fixture.sources:
        node_id = f"source:{source.source_id}"
        source_nodes[source.source_id] = node_id
        nodes.append(CausalAlphaFrontierLineageNode(node_id, "source", source.content_address, (source.source_id,)))
    for record in fixture.records:
        node_id = f"record:{record.record_id}"
        parents = tuple(source_nodes[item] for item in record.source_ids)
        nodes.append(CausalAlphaFrontierLineageNode(node_id, "record", record.content_address, record.source_ids, record.record_id, parents))
        edges.extend((parent, node_id, "supplies") for parent in parents)
    for result in evaluation.evaluation.results:
        node_id = f"result:{result.record_id}"
        record_id = f"record:{result.record_id}"
        nodes.append(CausalAlphaFrontierLineageNode(node_id, "result", result.content_address, (), result.record_id, (record_id,)))
        edges.append((record_id, node_id, "evaluates"))
    node_ids = {item.node_id for item in nodes}
    accepted = bool(len(nodes) == len(source_nodes) + len(fixture.records) + len(evaluation.evaluation.results) and all(parent in node_ids and child in node_ids for parent, child, _ in edges))
    return CausalAlphaFrontierLineage(fixture.fixture_id, tuple(nodes), tuple(edges), accepted)


__all__ = ["CausalAlphaFrontierLineage", "CausalAlphaFrontierLineageNode", "build_causal_alpha_frontier_lineage"]
