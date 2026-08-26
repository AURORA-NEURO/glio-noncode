"""Dependency graph projections for the static module inventory."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_inventory_contracts import ModuleInventory, ModuleRole, ModuleState
from .module_inventory_query import inventory_from_mapping
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ModuleGraphNode:
    """A module vertex with bounded degree summaries."""

    module_id: str
    family: str
    role: ModuleRole
    state: ModuleState
    incoming_count: int
    outgoing_count: int
    unresolved_outgoing_count: int
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.module_id.strip()
            or not self.family.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("module graph node identifiers are required")
        if min(self.incoming_count, self.outgoing_count, self.unresolved_outgoing_count) < 0:
            raise ValidationError("module graph node counts cannot be negative")
        if self.unresolved_outgoing_count > self.outgoing_count:
            raise ValidationError("unresolved graph edges cannot exceed outgoing edges")

    @property
    def degree(self) -> int:
        return self.incoming_count + self.outgoing_count

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"degree": self.degree}


@dataclass(frozen=True, slots=True)
class ModuleGraphEdge:
    """A unique source-to-target import edge."""

    source_module: str
    target_module: str
    import_names: tuple[str, ...]
    relative_import: bool
    resolved: bool
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.source_module.strip()
            or not self.target_module.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("module graph edge identifiers are required")
        if tuple(sorted(set(self.import_names))) != self.import_names:
            raise ValidationError("module graph import names must be unique and sorted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryGraph:
    """Addressed graph plus cycle and unresolved-edge summaries."""

    graph_id: str
    nodes: tuple[ModuleGraphNode, ...]
    edges: tuple[ModuleGraphEdge, ...]
    cycle_components: tuple[tuple[str, ...], ...]
    unresolved_edge_count: int
    root_modules: tuple[str, ...]
    leaf_modules: tuple[str, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.graph_id.strip() or not self.content_address.strip():
            raise ValidationError("module inventory graph identifiers are required")
        node_ids = {item.module_id for item in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValidationError("module graph node identifiers must be unique")
        if self.unresolved_edge_count < 0 or self.unresolved_edge_count > len(self.edges):
            raise ValidationError("module graph unresolved edge count is invalid")

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def cycle_count(self) -> int:
        return len(self.cycle_components)

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result = {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "cycle_count": self.cycle_count,
            "unresolved_edge_count": self.unresolved_edge_count,
            "root_modules": list(self.root_modules),
            "leaf_modules": list(self.leaf_modules),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_rows:
            result |= {
                "nodes": [item.to_dict() for item in self.nodes],
                "edges": [item.to_dict() for item in self.edges],
                "cycle_components": [list(item) for item in self.cycle_components],
            }
        return result


def _edge_address(body: Mapping[str, Any]) -> str:
    return content_hash(body, prefix="module-inventory-graph-edge")


def _node_address(body: Mapping[str, Any]) -> str:
    return content_hash(body, prefix="module-inventory-graph-node")


def _strongly_connected_components(
    nodes: tuple[str, ...],
    adjacency: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, ...], ...]:
    """Return stable Tarjan components, retaining only cycles."""

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in adjacency.get(node, ()):
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])
        if lowlinks[node] == indexes[node]:
            component: list[str] = []
            while stack:
                selected = stack.pop()
                on_stack.remove(selected)
                component.append(selected)
                if selected == node:
                    break
            ordered = tuple(sorted(component))
            if len(ordered) > 1 or ordered[0] in adjacency.get(ordered[0], ()):
                components.append(ordered)

    for node in nodes:
        if node not in indexes:
            visit(node)
    return tuple(sorted(components))


def build_module_inventory_graph(
    inventory: ModuleInventory | Mapping[str, Any],
    *,
    graph_id: str = "glio-noncode-module-inventory-graph",
) -> ModuleInventoryGraph:
    """Build a graph over discovered modules and explicit local imports."""

    value = (
        inventory if isinstance(inventory, ModuleInventory) else inventory_from_mapping(inventory)
    )
    module_by_id = {item.module_id: item for item in value.modules}
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    relative: dict[tuple[str, str], bool] = {}
    resolved: dict[tuple[str, str], bool] = {}
    for item in value.dependencies:
        key = (item.source_module, item.target_module)
        grouped[key].add(item.import_name)
        relative[key] = relative.get(key, False) or item.relative
        resolved[key] = (
            resolved.get(key, False) and item.resolved if key in resolved else item.resolved
        )
    edge_rows: list[ModuleGraphEdge] = []
    for key in sorted(grouped):
        source, target = key
        body = {
            "source_module": source,
            "target_module": target,
            "import_names": tuple(sorted(grouped[key])),
            "relative_import": relative[key],
            "resolved": resolved[key],
        }
        edge_rows.append(ModuleGraphEdge(**body, content_address=_edge_address(body)))
    incoming: dict[str, int] = defaultdict(int)
    outgoing: dict[str, int] = defaultdict(int)
    unresolved: dict[str, int] = defaultdict(int)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edge_rows:
        outgoing[edge.source_module] += 1
        if edge.target_module in module_by_id:
            incoming[edge.target_module] += 1
            adjacency[edge.source_module].add(edge.target_module)
        if not edge.resolved:
            unresolved[edge.source_module] += 1
    node_rows: list[ModuleGraphNode] = []
    for module_id in sorted(module_by_id):
        module = module_by_id[module_id]
        body = {
            "module_id": module_id,
            "family": module.family,
            "role": module.role,
            "state": module.state,
            "incoming_count": incoming[module_id],
            "outgoing_count": outgoing[module_id],
            "unresolved_outgoing_count": unresolved[module_id],
        }
        node_rows.append(ModuleGraphNode(**body, content_address=_node_address(body)))
    nodes = tuple(node_rows)
    edges = tuple(edge_rows)
    node_ids = set(module_by_id)
    roots = tuple(sorted(module_id for module_id in node_ids if incoming[module_id] == 0))
    leaves = tuple(sorted(module_id for module_id in node_ids if outgoing[module_id] == 0))
    cycles = _strongly_connected_components(
        tuple(sorted(node_ids)), {key: tuple(sorted(value)) for key, value in adjacency.items()}
    )
    unresolved_count = sum(not item.resolved for item in edges)
    body = {
        "graph_id": graph_id,
        "nodes": nodes,
        "edges": edges,
        "cycle_components": cycles,
        "unresolved_edge_count": unresolved_count,
        "root_modules": roots,
        "leaf_modules": leaves,
        "accepted": value.accepted,
    }
    return ModuleInventoryGraph(
        **body, content_address=content_hash(body, prefix="module-inventory-graph")
    )


def query_module_inventory_graph(
    graph: ModuleInventoryGraph,
    *,
    module_id: str | None = None,
    family: str | None = None,
    resolved: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded node and edge neighborhood."""

    if offset < 0 or limit < 1 or limit > 500:
        raise ValidationError("module graph paging is invalid")
    node_rows = [item.to_dict() for item in graph.nodes]
    if module_id is not None:
        node_rows = [item for item in node_rows if item["module_id"] == module_id]
    if family is not None:
        node_rows = [item for item in node_rows if item["family"] == family]
    edge_rows = [item.to_dict() for item in graph.edges]
    if module_id is not None:
        edge_rows = [
            item
            for item in edge_rows
            if item["source_module"] == module_id or item["target_module"] == module_id
        ]
    if resolved is not None:
        edge_rows = [item for item in edge_rows if item["resolved"] is resolved]
    if text:
        needle = text.casefold()
        node_rows = [item for item in node_rows if needle in str(item).casefold()]
        edge_rows = [item for item in edge_rows if needle in str(item).casefold()]
    combined = sorted(node_rows, key=lambda item: ("node", item["module_id"]))[
        offset : offset + limit
    ]
    selected_edges = sorted(
        edge_rows, key=lambda item: (item["source_module"], item["target_module"])
    )[:limit]
    body = {
        "graph_id": graph.graph_id,
        "query": {"module_id": module_id, "family": family, "resolved": resolved, "text": text},
        "node_total": len(node_rows),
        "edge_total": len(edge_rows),
        "offset": offset,
        "limit": limit,
        "nodes": combined,
        "edges": selected_edges,
        "accepted": graph.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-inventory-graph-query")}


def module_inventory_graph_schema() -> dict[str, Any]:
    return {
        "version": "module-inventory-graph-v1",
        "node_fields": [
            "module_id",
            "family",
            "role",
            "state",
            "incoming_count",
            "outgoing_count",
            "unresolved_outgoing_count",
            "content_address",
        ],
        "edge_fields": [
            "source_module",
            "target_module",
            "import_names",
            "relative_import",
            "resolved",
            "content_address",
        ],
        "guarantees": [
            "nodes are source modules",
            "edges are import relationships",
            "unresolved edges remain visible",
            "cycles are reported as stable components",
        ],
    }


def module_inventory_graph_capabilities() -> dict[str, Any]:
    operations = (
        "build_dependency_graph",
        "compute_degree_summary",
        "detect_cycles",
        "identify_roots_and_leaves",
        "query_graph_neighborhood",
    )
    return {
        "version": "module-inventory-graph-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
    }


__all__ = [
    "ModuleGraphEdge",
    "ModuleGraphNode",
    "ModuleInventoryGraph",
    "build_module_inventory_graph",
    "module_inventory_graph_capabilities",
    "module_inventory_graph_schema",
    "query_module_inventory_graph",
]
