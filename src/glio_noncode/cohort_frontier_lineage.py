"""Cohort source and execution lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_public_data import CohortFrontierFixture
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierLineageEdge:
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
class CohortFrontierLineageGraph:
    fixture_id: str
    root_addresses: tuple[str, ...]
    edges: tuple[CohortFrontierLineageEdge, ...]
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
        visited: set[str] = set()
        visiting: set[str] = set()
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


def build_cohort_frontier_lineage(fixture: CohortFrontierFixture, evaluation: CohortFrontierEvaluation) -> CohortFrontierLineageGraph:
    source_map = fixture.source_map()
    edges: list[CohortFrontierLineageEdge] = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        for source_id in record.source_ids:
            body = {"edge_id": f"{record.record_id}:{source_id}", "parent_address": source_map[source_id].content_address, "child_address": execution.content_address, "edge_kind": "source_to_execution", "operation": record.operation.value, "explanation": record.description}
            edges.append(CohortFrontierLineageEdge(**body, content_address=content_hash(body)))
        body = {"edge_id": f"{record.record_id}:fixture", "parent_address": fixture.content_address, "child_address": execution.content_address, "edge_kind": "fixture_to_execution", "operation": record.operation.value, "explanation": "fixture record is replayed into an execution receipt"}
        edges.append(CohortFrontierLineageEdge(**body, content_address=content_hash(body))
        )
    body = {"fixture_id": fixture.fixture_id, "root_addresses": tuple(item.content_address for item in fixture.sources) + (fixture.content_address,), "edges": tuple(edges), "terminal_addresses": tuple(item.content_address for item in evaluation.executions)}
    return CohortFrontierLineageGraph(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierLineageEdge", "CohortFrontierLineageGraph", "build_cohort_frontier_lineage"]
