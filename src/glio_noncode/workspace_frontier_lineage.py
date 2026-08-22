"""Acyclic source-to-workspace lineage for the frontier fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_public_data import WorkspaceFrontierFixture


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierLineageEdge:
    edge_id: str
    parent_id: str
    child_id: str
    relation: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("edge_id", "parent_id", "child_id", "relation", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.parent_id == self.child_id:
            raise ValueError("workspace lineage cannot self-reference")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierLineageGraph:
    fixture_id: str
    edges: tuple[WorkspaceFrontierLineageEdge, ...]
    root_ids: tuple[str, ...]
    terminal_addresses: tuple[str, ...]
    acyclic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_workspace_frontier_lineage(fixture: WorkspaceFrontierFixture, evaluation: WorkspaceFrontierEvaluation) -> WorkspaceFrontierLineageGraph:
    edges: list[WorkspaceFrontierLineageEdge] = []
    for source in fixture.sources:
        for operation in sorted({item.operation.value for item in fixture.records}):
            child = f"operation:{operation}"
            body = {"edge_id": f"source:{source.source_id}:{operation}", "parent_id": f"source:{source.source_id}", "child_id": child, "relation": "declares-surface"}
            edges.append(WorkspaceFrontierLineageEdge(**body, content_address=content_hash(body)))
    for execution in evaluation.executions:
        body = {"edge_id": f"record:{execution.record_id}", "parent_id": f"operation:{execution.operation.value}", "child_id": f"execution:{execution.record_id}", "relation": "executes-record"}
        edges.append(WorkspaceFrontierLineageEdge(**body, content_address=content_hash(body)))
    edge_ids = {item.edge_id for item in edges}
    acyclic = len(edge_ids) == len(edges) and all(item.parent_id != item.child_id for item in edges)
    terminals = tuple(item.content_address for item in evaluation.executions)
    body = {"fixture_id": fixture.fixture_id, "edges": tuple(edges), "root_ids": tuple(f"source:{item.source_id}" for item in fixture.sources), "terminal_addresses": terminals, "acyclic": acyclic}
    return WorkspaceFrontierLineageGraph(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierLineageEdge", "WorkspaceFrontierLineageGraph", "build_workspace_frontier_lineage"]
