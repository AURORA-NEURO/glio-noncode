"""Connected dependency graph for all D15 closure rows and source artifacts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_offline_closure_contracts import (
    WorkbenchReleaseClosureGraphEdge,
    WorkbenchReleaseClosureGraphReport,
)
from .workbench_release_frontier_offline_closure_support import all_rows
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

WORKBENCH_RELEASE_CLOSURE_GRAPH_VERSION = "workbench-release-closure-graph-v1"

_ARTIFACT_BY_RESOURCE = {
    "artifacts": "artifacts",
    "records": "fixture",
    "executions": "evaluation",
    "checks": "evaluation",
    "sources": "source-registry",
    "validation": "validation",
    "evidence": "evidence",
    "edges": "lineage",
    "views": "view",
    "queue": "review-queue",
    "diagnostics": "diagnostics",
    "stages": "runtime",
    "stage_index": "stage-index",
    "operations": "operation-index",
    "controls": "controls",
    "failures": "failure-injection",
}


def _row_node(resource: str, row: dict[str, Any], ordinal: int) -> str:
    identity = (
        row.get("record_id")
        or row.get("check_id")
        or row.get("source_id")
        or row.get("stage_id")
        or row.get("edge_id")
        or row.get("operation")
        or row.get("case")
        or f"{ordinal:04d}"
    )
    return f"row:{resource}:{identity}"


def _artifact_node(artifact_id: str) -> str:
    return f"artifact:{artifact_id}"


def _edge(
    source: str, target: str, relation: str, ordinal: int
) -> WorkbenchReleaseClosureGraphEdge:
    edge_id = f"{source}->{target}:{relation}:{ordinal:05d}"
    body = {"edge_id": edge_id, "source": source, "target": target, "relation": relation}
    return WorkbenchReleaseClosureGraphEdge(
        **body,
        address=content_hash(body, prefix="workbench-release-closure-graph-edge"),
    )


def _components(nodes: set[str], edges: tuple[WorkbenchReleaseClosureGraphEdge, ...]) -> int:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for item in edges:
        adjacency[item.source].add(item.target)
        adjacency[item.target].add(item.source)
    remaining = set(nodes)
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            current = stack.pop()
            for target in adjacency[current]:
                if target in remaining:
                    remaining.remove(target)
                    stack.append(target)
    return count


def build_workbench_release_closure_graph(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureGraphReport:
    rows = all_rows(bundle)
    nodes: set[str] = {f"bundle:{bundle.bundle_id}"}
    edges: list[WorkbenchReleaseClosureGraphEdge] = []
    artifact_ids = tuple(item.artifact_id for item in bundle.artifacts)
    for artifact_id in artifact_ids:
        node = _artifact_node(artifact_id)
        nodes.add(node)
        edges.append(_edge(f"bundle:{bundle.bundle_id}", node, "contains_artifact", len(edges) + 1))
    row_nodes: dict[str, dict[str, str]] = defaultdict(dict)
    for resource, values in rows.items():
        artifact_id = _ARTIFACT_BY_RESOURCE[resource]
        artifact_node = _artifact_node(artifact_id)
        for ordinal, row in enumerate(values, 1):
            node = _row_node(resource, row, ordinal)
            nodes.add(node)
            row_nodes[resource][
                str(
                    row.get("record_id")
                    or row.get("check_id")
                    or row.get("source_id")
                    or row.get("stage_id")
                    or row.get("edge_id")
                    or row.get("operation")
                    or row.get("case")
                    or ordinal
                )
            ] = node
            edges.append(_edge(artifact_node, node, f"materializes_{resource}", len(edges) + 1))
    for row in rows["edges"]:
        parent = str(row.get("parent_id"))
        child = str(row.get("child_id"))
        relation = str(row.get("relation"))
        source = (
            row_nodes["sources"].get(parent)
            if relation == "source_to_record"
            else row_nodes["records"].get(parent)
        )
        target = (
            row_nodes["records"].get(child)
            if relation == "source_to_record"
            else row_nodes["executions"].get(child)
        )
        if source and target:
            edges.append(_edge(source, target, relation, len(edges) + 1))
    for row in rows["records"]:
        record_id = str(row.get("record_id"))
        record = row_nodes["records"].get(record_id)
        if not record:
            continue
        for resource in ("executions", "views", "queue", "diagnostics", "evidence"):
            target = row_nodes[resource].get(record_id)
            if target:
                edges.append(_edge(record, target, f"record_to_{resource}", len(edges) + 1))
        for check in rows["checks"]:
            if str(check.get("record_id")) == record_id:
                target = row_nodes["checks"].get(str(check.get("check_id")))
                if target:
                    edges.append(_edge(record, target, "record_to_check", len(edges) + 1))
        for cell in rows["validation"]:
            if str(cell.get("record_id")) == record_id:
                target = row_nodes["validation"].get(record_id)
                if target:
                    edges.append(_edge(record, target, "record_to_validation", len(edges) + 1))
    for row in rows["operations"]:
        operation = str(row.get("operation"))
        operation_node = row_nodes["operations"].get(operation)
        if operation_node:
            for record in rows["records"]:
                if str(record.get("operation")) == operation:
                    target = row_nodes["records"].get(str(record.get("record_id")))
                    if target:
                        edges.append(
                            _edge(operation_node, target, "operation_to_record", len(edges) + 1)
                        )
    for row in rows["stage_index"]:
        stage_id = str(row.get("stage_id"))
        index_node = row_nodes["stage_index"].get(stage_id)
        stage_node = row_nodes["stages"].get(stage_id)
        if index_node and stage_node:
            edges.append(_edge(index_node, stage_node, "stage_index_to_stage", len(edges) + 1))
    edges_tuple = tuple(edges)
    components = _components(nodes, edges_tuple)
    body = {
        "bundle_id": bundle.bundle_id,
        "nodes": tuple(sorted(nodes)),
        "edges": edges_tuple,
        "connected_component_count": components,
        "accepted": components == 1 and len(nodes) > 350 and len(edges_tuple) > len(nodes),
    }
    return WorkbenchReleaseClosureGraphReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-graph"),
    )


def audit_workbench_release_closure_graph(
    graph: WorkbenchReleaseClosureGraphReport,
) -> tuple[Any, ...]:
    from .workbench_release_frontier_offline_closure_contracts import (
        workbench_release_closure_check,
    )

    node_set = set(graph.nodes)
    checks = (
        workbench_release_closure_check(
            "graph-accepted", "graph", graph.accepted, graph.accepted, True, "graph is accepted"
        ),
        workbench_release_closure_check(
            "graph-nodes",
            "graph",
            len(node_set) > 350,
            len(node_set),
            ">350",
            "graph retains a deep node inventory",
        ),
        workbench_release_closure_check(
            "graph-unique-nodes",
            "graph",
            len(node_set) == len(graph.nodes),
            len(node_set),
            len(graph.nodes),
            "graph nodes are unique",
        ),
        workbench_release_closure_check(
            "graph-edges",
            "graph",
            len(graph.edges) > len(graph.nodes),
            len(graph.edges),
            f">{len(graph.nodes)}",
            "graph has relationship depth",
        ),
        workbench_release_closure_check(
            "graph-edge-addresses",
            "graph",
            all(item.address for item in graph.edges),
            sum(bool(item.address) for item in graph.edges),
            len(graph.edges),
            "graph edges are addressed",
        ),
        workbench_release_closure_check(
            "graph-single-component",
            "graph",
            graph.connected_component_count == 1,
            graph.connected_component_count,
            1,
            "all public closure nodes are connected",
        ),
    )
    return checks


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_GRAPH_VERSION",
    "audit_workbench_release_closure_graph",
    "build_workbench_release_closure_graph",
]
