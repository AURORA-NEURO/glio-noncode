"""Typed source-to-execution lineage for sequence-effect outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectLineageNode:
    node_id: str
    node_kind: str
    address: str
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectLineageEdge:
    source_id: str
    target_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectLineage:
    nodes: tuple[SequenceEffectLineageNode, ...]
    edges: tuple[SequenceEffectLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"nodes": self.nodes, "edges": self.edges, "accepted": self.accepted}),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "content_address": self.content_address,
        }


def build_sequence_effect_lineage(
    fixture: SequenceEffectFixture, evaluation: SequenceEffectEvaluation
) -> SequenceEffectLineage:
    nodes: list[SequenceEffectLineageNode] = [
        SequenceEffectLineageNode(
            f"source:{source.source_id}",
            "source",
            source.content_address,
            {"source_id": source.source_id, "context_key": source.context_key},
        )
        for source in fixture.sources
    ]
    nodes.append(
        SequenceEffectLineageNode(
            f"fixture:{fixture.fixture_id}",
            "fixture",
            fixture.content_address,
            {"fixture_id": fixture.fixture_id, "context_key": fixture.context_key},
        )
    )
    edges: list[SequenceEffectLineageEdge] = []
    for source in fixture.sources:
        edges.append(
            SequenceEffectLineageEdge(
                f"source:{source.source_id}",
                f"fixture:{fixture.fixture_id}",
                "declared-source",
                content_hash(
                    {
                        "source": source.source_id,
                        "fixture": fixture.fixture_id,
                        "relation": "declared-source",
                    }
                ),
            )
        )
    for execution in evaluation.executions:
        node_id = f"execution:{execution.record_id}"
        nodes.append(
            SequenceEffectLineageNode(
                node_id,
                "execution",
                execution.content_address,
                {
                    "record_id": execution.record_id,
                    "operation": execution.operation.value,
                    "state": execution.adapter_state.value,
                },
            )
        )
        edges.append(
            SequenceEffectLineageEdge(
                f"fixture:{fixture.fixture_id}",
                node_id,
                "executes",
                content_hash(
                    {
                        "fixture": fixture.fixture_id,
                        "execution": execution.record_id,
                        "relation": "executes",
                    }
                ),
            )
        )
        for source_id in execution.source_ids:
            edges.append(
                SequenceEffectLineageEdge(
                    f"source:{source_id}",
                    node_id,
                    "supports",
                    content_hash(
                        {
                            "source": source_id,
                            "execution": execution.record_id,
                            "relation": "supports",
                        }
                    ),
                )
            )
    node_ids = {node.node_id for node in nodes}
    accepted = all(
        edge.source_id in node_ids
        and edge.target_id in node_ids
        and edge.content_address.startswith("sha256:")
        for edge in edges
    ) and len({node.address for node in nodes}) == len(nodes)
    return SequenceEffectLineage(tuple(nodes), tuple(edges), accepted)


def verify_sequence_effect_lineage(
    lineage: SequenceEffectLineage,
    fixture: SequenceEffectFixture,
    evaluation: SequenceEffectEvaluation,
) -> bool:
    expected_execution_ids = {f"execution:{item.record_id}" for item in evaluation.executions}
    actual_execution_ids = {node.node_id for node in lineage.nodes if node.node_kind == "execution"}
    return (
        lineage.accepted
        and expected_execution_ids == actual_execution_ids
        and any(node.node_id == f"fixture:{fixture.fixture_id}" for node in lineage.nodes)
    )


__all__ = [
    "SequenceEffectLineage",
    "SequenceEffectLineageEdge",
    "SequenceEffectLineageNode",
    "build_sequence_effect_lineage",
    "verify_sequence_effect_lineage",
]
