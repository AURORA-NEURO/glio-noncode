"""Acyclic source-to-projection lineage for the C05-C08 package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_public_data import BetaFrontierFixture


@dataclass(frozen=True, slots=True)
class BetaFrontierLineageEdge:
    """One directed receipt edge."""

    edge_id: str
    parent_address: str
    child_address: str
    relation: str
    record_id: str | None
    operation: str | None
    content_address: str

    def __post_init__(self) -> None:
        for name in ("edge_id", "parent_address", "child_address", "relation", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.parent_address == self.child_address:
            raise ValueError("beta frontier lineage cannot self-link")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierLineageGraph:
    """Source and execution graph with deterministic order and cycle status."""

    fixture_id: str
    nodes: tuple[str, ...]
    edges: tuple[BetaFrontierLineageEdge, ...]
    root_addresses: tuple[str, ...]
    leaf_addresses: tuple[str, ...]
    acyclic: bool
    content_address: str

    def children_of(self, address: str) -> tuple[str, ...]:
        return tuple(edge.child_address for edge in self.edges if edge.parent_address == address)

    def parents_of(self, address: str) -> tuple[str, ...]:
        return tuple(edge.parent_address for edge in self.edges if edge.child_address == address)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _edge(index: int, parent: str, child: str, relation: str, record_id: str | None, operation: str | None) -> BetaFrontierLineageEdge:
    body = {"edge_id": f"lineage-edge-{index:03d}", "parent_address": parent, "child_address": child, "relation": relation, "record_id": record_id, "operation": operation}
    return BetaFrontierLineageEdge(**body, content_address=content_hash(body))


def build_beta_frontier_lineage(fixture: BetaFrontierFixture, evaluation: BetaFrontierEvaluation) -> BetaFrontierLineageGraph:
    """Build source, row, and execution edges while retaining every receipt."""

    nodes: set[str] = {fixture.content_address}
    edges: list[BetaFrontierLineageEdge] = []
    index = 1
    for source in fixture.sources:
        nodes.add(source.content_address)
        edges.append(_edge(index, source.content_address, fixture.content_address, "source_to_fixture", None, None))
        index += 1
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        nodes.update((record.content_address, execution.content_address))
        edges.append(_edge(index, fixture.content_address, record.content_address, "fixture_to_projection_case", record.record_id, record.operation.value))
        index += 1
        edges.append(_edge(index, record.content_address, execution.content_address, "case_to_execution", record.record_id, record.operation.value))
        index += 1
    parent_map = {edge.child_address: edge.parent_address for edge in edges}
    roots = tuple(sorted(node for node in nodes if node not in parent_map))
    children = {edge.parent_address for edge in edges}
    leaves = tuple(sorted(node for node in nodes if node not in children))
    graph_nodes = tuple(sorted(nodes))
    body = {"fixture_id": fixture.fixture_id, "nodes": graph_nodes, "edges": tuple(edges), "root_addresses": roots, "leaf_addresses": leaves, "acyclic": True}
    return BetaFrontierLineageGraph(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierLineageEdge", "BetaFrontierLineageGraph", "build_beta_frontier_lineage"]
