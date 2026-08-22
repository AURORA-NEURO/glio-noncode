"""Sanitized source-to-result lineage for the motif grammar fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import SequenceGrammarFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarLineageNode:
    node_id: str
    node_kind: str
    label: str
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.node_id.strip()
            or not self.node_kind.strip()
            or not self.content_address.startswith("sha256:")
        ):
            raise ValidationError("lineage node is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarLineageEdge:
    edge_id: str
    from_node: str
    to_node: str
    relation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.edge_id.strip()
            or not self.from_node.strip()
            or not self.to_node.strip()
            or not self.relation.strip()
        ):
            raise ValidationError("lineage edge is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "edge_id": self.edge_id,
                        "from": self.from_node,
                        "to": self.to_node,
                        "relation": self.relation,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarLineage:
    fixture_id: str
    nodes: tuple[SequenceGrammarLineageNode, ...]
    edges: tuple[SequenceGrammarLineageEdge, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.nodes or not self.edges:
            raise ValidationError("lineage requires nodes and edges")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture_id": self.fixture_id,
                        "nodes": self.nodes,
                        "edges": self.edges,
                        "accepted": self.accepted,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "accepted": self.accepted,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "content_address": self.content_address,
        }


def build_sequence_grammar_lineage(
    fixture: SequenceGrammarFixture, evaluation: SequenceGrammarEvaluation
) -> SequenceGrammarLineage:
    nodes: list[SequenceGrammarLineageNode] = []
    edges: list[SequenceGrammarLineageEdge] = []
    nodes.append(
        SequenceGrammarLineageNode(
            f"fixture:{fixture.fixture_id}", "fixture", fixture.fixture_id, fixture.content_address
        )
    )
    for source in fixture.sources:
        node_id = f"source:{source.source_id}"
        nodes.append(
            SequenceGrammarLineageNode(node_id, "source", source.source_id, source.content_address)
        )
        edges.append(
            SequenceGrammarLineageEdge(
                f"edge:{node_id}:fixture",
                node_id,
                f"fixture:{fixture.fixture_id}",
                "supports_fixture",
            )
        )
    for record in fixture.records:
        record_node = f"record:{record.record_id}"
        nodes.append(
            SequenceGrammarLineageNode(
                record_node, "record", record.record_id, record.content_address
            )
        )
        edges.append(
            SequenceGrammarLineageEdge(
                f"edge:fixture:{record.record_id}",
                f"fixture:{fixture.fixture_id}",
                record_node,
                "contains_record",
            )
        )
        for source_id in record.source_ids:
            edges.append(
                SequenceGrammarLineageEdge(
                    f"edge:source:{source_id}:{record.record_id}",
                    f"source:{source_id}",
                    record_node,
                    "supports_record",
                )
            )
    for execution in evaluation.executions:
        execution_node = f"execution:{execution.record_id}"
        nodes.append(
            SequenceGrammarLineageNode(
                execution_node, "execution", execution.record_id, execution.content_address
            )
        )
        edges.append(
            SequenceGrammarLineageEdge(
                f"edge:record:{execution.record_id}:execution",
                f"record:{execution.record_id}",
                execution_node,
                "executed_as",
            )
        )
        for issue_code in execution.issue_codes:
            issue_node = f"issue:{issue_code}"
            if not any(node.node_id == issue_node for node in nodes):
                nodes.append(
                    SequenceGrammarLineageNode(
                        issue_node, "issue", issue_code, content_hash({"issue_code": issue_code})
                    )
                )
            edges.append(
                SequenceGrammarLineageEdge(
                    f"edge:{execution.record_id}:{issue_code}",
                    execution_node,
                    issue_node,
                    "retains_boundary",
                )
            )
    node_ids = {node.node_id for node in nodes}
    accepted = len(node_ids) == len(nodes) and all(
        edge.from_node in node_ids and edge.to_node in node_ids for edge in edges
    )
    return SequenceGrammarLineage(fixture.fixture_id, tuple(nodes), tuple(edges), accepted)


def verify_sequence_grammar_lineage(
    lineage: SequenceGrammarLineage,
    fixture: SequenceGrammarFixture,
    evaluation: SequenceGrammarEvaluation,
) -> bool:
    node_ids = {node.node_id for node in lineage.nodes}
    expected_records = {f"record:{record.record_id}" for record in fixture.records}
    expected_executions = {
        f"execution:{execution.record_id}" for execution in evaluation.executions
    }
    return (
        lineage.accepted
        and expected_records <= node_ids
        and expected_executions <= node_ids
        and all(edge.from_node in node_ids and edge.to_node in node_ids for edge in lineage.edges)
    )


__all__ = [
    "SequenceGrammarLineage",
    "SequenceGrammarLineageEdge",
    "SequenceGrammarLineageNode",
    "build_sequence_grammar_lineage",
    "verify_sequence_grammar_lineage",
]
