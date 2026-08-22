"""Source-to-result lineage for topology context records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import TopologyContextFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierLineageEdge:
    edge_id: str
    source_id: str
    record_id: str
    result_address: str
    relationship: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierLineage:
    edges: tuple[TopologyContextFrontierLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def node_addresses(self) -> tuple[str, ...]:
        return tuple(sorted({item.result_address for item in self.edges}))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "edges": [item.to_dict() for item in self.edges],
            "accepted": self.accepted,
            "node_addresses": self.node_addresses,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_lineage(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierLineage:
    source_map = {item.record_id: item.source_ids[0] for item in fixture.records}
    edges = tuple(
        TopologyContextFrontierLineageEdge(
            f"edge-{item.record_id}",
            source_map[item.record_id],
            item.record_id,
            item.adapter.content_address,
            "source_to_result",
        )
        for item in evaluation.rows
    )
    return TopologyContextFrontierLineage(edges=edges, accepted=len(edges) == len(fixture.records))


__all__ = [
    "TopologyContextFrontierLineage",
    "TopologyContextFrontierLineageEdge",
    "build_topology_context_frontier_lineage",
]
