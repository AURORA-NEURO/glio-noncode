"""Source, transform, and output lineage for causal frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_public_data import CausalFrontierFixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierLineageEdge:
    edge_id: str
    parent_address: str
    child_address: str
    edge_kind: str
    operation: str
    explanation: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("edge_id", "parent_address", "child_address", "edge_kind", "operation", "explanation"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierLineageGraph:
    fixture_id: str
    root_addresses: tuple[str, ...]
    edges: tuple[CausalFrontierLineageEdge, ...]
    terminal_addresses: tuple[str, ...]
    content_address: str

    @property
    def node_addresses(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.root_addresses) | {item.parent_address for item in self.edges} | {item.child_address for item in self.edges}))

    @property
    def acyclic(self) -> bool:
        adjacency: dict[str, set[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.parent_address, set()).add(edge.child_address)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return False
            if node in visited:
                return True
            visiting.add(node)
            if any(not visit(child) for child in adjacency.get(node, ())):
                return False
            visiting.remove(node)
            visited.add(node)
            return True

        return all(visit(node) for node in self.root_addresses)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"node_addresses": list(self.node_addresses), "acyclic": self.acyclic}


def build_causal_frontier_lineage(
    fixture: CausalFrontierFixture,
    evaluation: CausalFrontierEvaluation,
) -> CausalFrontierLineageGraph:
    roots = tuple(item.content_address for item in fixture.sources)
    edges: list[CausalFrontierLineageEdge] = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        for source in record.source_ids:
            parent = fixture.source_map()[source].content_address
            body = {
                "edge_id": f"{record.record_id}:{source}",
                "parent_address": parent,
                "child_address": execution.content_address,
                "edge_kind": "source_to_execution",
                "operation": record.operation.value,
                "explanation": record.description,
            }
            edges.append(CausalFrontierLineageEdge(**body, content_address=content_hash(body)))
        body = {
            "edge_id": f"{record.record_id}:fixture",
            "parent_address": fixture.content_address,
            "child_address": execution.content_address,
            "edge_kind": "fixture_to_execution",
            "operation": record.operation.value,
            "explanation": "fixture record is replayed into a deterministic execution receipt",
        }
        edges.append(CausalFrontierLineageEdge(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "root_addresses": roots + (fixture.content_address,),
        "edges": tuple(edges),
        "terminal_addresses": tuple(item.content_address for item in evaluation.executions),
    }
    return CausalFrontierLineageGraph(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierLineageEdge", "CausalFrontierLineageGraph", "build_causal_frontier_lineage"]
