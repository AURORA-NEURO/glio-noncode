"""Redacted source-to-execution lineage for control frontier rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierLineageEdge:
    edge_id: str
    parent_id: str
    child_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierLineage:
    fixture_id: str
    nodes: tuple[str, ...]
    edges: tuple[ControlFrontierLineageEdge, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_lineage(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation) -> ControlFrontierLineage:
    nodes = [fixture.fixture_id, *[source.source_id for source in fixture.sources], *[item.record_id for item in fixture.records], *[item.record_id + ":execution" for item in evaluation.executions]]
    edges: list[ControlFrontierLineageEdge] = []
    for record in fixture.records:
        for source_id in record.source_ids:
            body = {"edge_id": f"{source_id}->{record.record_id}", "parent_id": source_id, "child_id": record.record_id, "relation": "source_supports_record"}
            edges.append(ControlFrontierLineageEdge(**body, content_address=content_hash(body)))
        body = {"edge_id": f"{record.record_id}->{record.record_id}:execution", "parent_id": record.record_id, "child_id": f"{record.record_id}:execution", "relation": "record_executes"}
        edges.append(ControlFrontierLineageEdge(**body, content_address=content_hash(body)))
    accepted = len(nodes) == len(set(nodes)) and all(edge.parent_id in nodes and edge.child_id in nodes for edge in edges)
    body = {"fixture_id": fixture.fixture_id, "nodes": tuple(nodes), "edges": tuple(edges), "accepted": accepted}
    return ControlFrontierLineage(**body, content_address=content_hash(body))


def verify_control_frontier_lineage(lineage: ControlFrontierLineage) -> tuple[str, ...]:
    issues = []
    if len(lineage.nodes) != len(set(lineage.nodes)):
        issues.append("duplicate_node")
    if any(edge.parent_id not in lineage.nodes or edge.child_id not in lineage.nodes for edge in lineage.edges):
        issues.append("dangling_edge")
    return tuple(issues)


__all__ = ["ControlFrontierLineage", "ControlFrontierLineageEdge", "build_control_frontier_lineage", "verify_control_frontier_lineage"]
