"""Connected dependency graph for D16 artifacts, rows, stages, and receipts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DeploymentFrontierClosureGraphEdge,
    DeploymentFrontierClosureGraphReport,
)
from .deployment_frontier_offline_closure_support import all_rows
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash

_ARTIFACT_BY_RESOURCE = {
    "artifacts": "artifacts",
    "records": "fixture",
    "executions": "evaluation",
    "checks": "evaluation",
    "sources": "fixture",
    "validation": "validation",
    "evidence": "evaluation",
    "edges": "lineage",
    "views": "view",
    "queue": "queue",
    "diagnostics": "diagnostics",
    "stages": "runtime",
    "stage_index": "stage-index",
    "operations": "operation-index",
    "controls": "fixture",
    "failures": "failure_injection",
    "audit_events": "audit_log",
    "transcript_events": "transcript",
    "trace_observations": "trace",
}


def _identity(row: dict[str, Any], ordinal: int) -> str:
    for key in (
        "record_id",
        "check_id",
        "source_id",
        "stage_id",
        "edge_id",
        "finding_id",
        "cell_id",
        "event_id",
        "control_id",
        "probe_id",
        "operation",
        "queue_id",
    ):
        if row.get(key) not in (None, ""):
            return str(row[key])
    if row.get("sequence") not in (None, ""):
        return f"sequence-{row['sequence']}"
    return f"ordinal-{ordinal:04d}"


def _node(resource: str, row: dict[str, Any], ordinal: int) -> str:
    return f"row:{resource}:{_identity(row, ordinal)}:{ordinal:04d}"


def _artifact_node(artifact_id: str) -> str:
    return f"artifact:{artifact_id}"


def _edge(
    source: str, target: str, relation: str, ordinal: int
) -> DeploymentFrontierClosureGraphEdge:
    edge_id = f"{source}->{target}:{relation}:{ordinal:06d}"
    body = {"edge_id": edge_id, "source": source, "target": target, "relation": relation}
    return DeploymentFrontierClosureGraphEdge(
        **body, address=content_hash(body, prefix="deployment-frontier-closure-graph-edge")
    )


def _components(nodes: set[str], edges: tuple[DeploymentFrontierClosureGraphEdge, ...]) -> int:
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


def build_deployment_frontier_closure_graph(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureGraphReport:
    rows = all_rows(bundle)
    root = f"bundle:{bundle.bundle_id}"
    nodes: set[str] = {root}
    edges: list[DeploymentFrontierClosureGraphEdge] = []
    for artifact in bundle.artifacts:
        artifact_node = _artifact_node(artifact.artifact_id)
        nodes.add(artifact_node)
        edges.append(_edge(root, artifact_node, "contains_artifact", len(edges) + 1))
    row_nodes: dict[str, dict[str, str]] = defaultdict(dict)
    row_nodes_by_ordinal: dict[str, tuple[str, ...]] = {}
    for resource, values in rows.items():
        artifact_node = _artifact_node(_ARTIFACT_BY_RESOURCE[resource])
        created = []
        for ordinal, row in enumerate(values, 1):
            node = _node(resource, row, ordinal)
            created.append(node)
            nodes.add(node)
            row_nodes[resource][_identity(row, ordinal)] = node
            edges.append(_edge(artifact_node, node, f"materializes_{resource}", len(edges) + 1))
        row_nodes_by_ordinal[resource] = tuple(created)
    for row in rows["edges"]:
        relation = str(row.get("relation"))
        parent_id = str(row.get("parent_id"))
        child_id = str(row.get("child_id"))
        if relation == "supports":
            source = row_nodes["sources"].get(parent_id)
            target = row_nodes["records"].get(child_id)
        else:
            source = row_nodes["records"].get(parent_id)
            target = row_nodes["executions"].get(child_id.removeprefix("execution:"))
        if source and target:
            edges.append(_edge(source, target, relation, len(edges) + 1))
    for row in rows["records"]:
        record_id = str(row.get("record_id"))
        source = row_nodes["records"].get(record_id)
        if not source:
            continue
        for resource in ("executions", "views", "evidence", "queue"):
            target = row_nodes[resource].get(record_id)
            if target:
                edges.append(_edge(source, target, f"record_to_{resource}", len(edges) + 1))
        for check in rows["checks"]:
            if str(check.get("record_id")) == record_id:
                target = row_nodes["checks"].get(str(check.get("check_id")))
                if target:
                    edges.append(_edge(source, target, "record_to_check", len(edges) + 1))
        for cell in rows["validation"]:
            if str(cell.get("record_id")) == record_id:
                target = row_nodes["validation"].get(str(cell.get("cell_id")))
                if target:
                    edges.append(_edge(source, target, "record_to_validation", len(edges) + 1))
        for finding in rows["diagnostics"]:
            if str(finding.get("record_id")) == record_id:
                target = row_nodes["diagnostics"].get(str(finding.get("finding_id")))
                if target:
                    edges.append(_edge(source, target, "record_to_diagnostic", len(edges) + 1))
    for operation in rows["operations"]:
        operation_id = str(operation.get("operation"))
        source = row_nodes["operations"].get(operation_id)
        if source:
            for record in rows["records"]:
                if str(record.get("operation")) == operation_id:
                    target = row_nodes["records"].get(str(record.get("record_id")))
                    if target:
                        edges.append(_edge(source, target, "operation_to_record", len(edges) + 1))
    for index_row in rows["stage_index"]:
        stage_id = str(index_row.get("stage_id"))
        source = row_nodes["stage_index"].get(stage_id)
        target = row_nodes["stages"].get(stage_id)
        if source and target:
            edges.append(_edge(source, target, "stage_index_to_stage", len(edges) + 1))
    for resource in ("audit_events", "transcript_events", "trace_observations"):
        for row in rows[resource]:
            sequence = str(row.get("sequence"))
            source = row_nodes[resource].get(_identity(row, int(row.get("ordinal", 1))))
            stage = next(
                (item for item in rows["stages"] if str(item.get("sequence")) == sequence), None
            )
            target = (
                row_nodes["stages"].get(_identity(stage, int(stage.get("ordinal", 1))))
                if stage
                else None
            )
            if source and target:
                edges.append(_edge(source, target, f"{resource}_to_stage", len(edges) + 1))
    graph_edges = tuple(edges)
    components = _components(nodes, graph_edges)
    body = {
        "bundle_id": bundle.bundle_id,
        "nodes": tuple(sorted(nodes)),
        "edges": graph_edges,
        "connected_component_count": components,
        "accepted": components == 1 and len(nodes) > 500 and len(graph_edges) > len(nodes),
    }
    return DeploymentFrontierClosureGraphReport(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-graph")
    )


def audit_deployment_frontier_closure_graph(
    graph: DeploymentFrontierClosureGraphReport,
) -> tuple[Any, ...]:
    from .deployment_frontier_offline_closure_contracts import deployment_frontier_closure_check

    checks = (
        deployment_frontier_closure_check(
            "graph-accepted", "graph", graph.accepted, graph.accepted, True, "graph is accepted"
        ),
        deployment_frontier_closure_check(
            "graph-nodes",
            "graph",
            len(graph.nodes) > 500,
            len(graph.nodes),
            ">500",
            "graph retains deep nodes",
        ),
        deployment_frontier_closure_check(
            "graph-unique-nodes",
            "graph",
            len(set(graph.nodes)) == len(graph.nodes),
            len(set(graph.nodes)),
            len(graph.nodes),
            "graph nodes are unique",
        ),
        deployment_frontier_closure_check(
            "graph-edges",
            "graph",
            len(graph.edges) > len(graph.nodes),
            len(graph.edges),
            f">{len(graph.nodes)}",
            "graph retains relationship depth",
        ),
        deployment_frontier_closure_check(
            "graph-addresses",
            "graph",
            all(item.address for item in graph.edges),
            sum(bool(item.address) for item in graph.edges),
            len(graph.edges),
            "graph edges are addressed",
        ),
        deployment_frontier_closure_check(
            "graph-components",
            "graph",
            graph.connected_component_count == 1,
            graph.connected_component_count,
            1,
            "all closure nodes are connected",
        ),
    )
    return checks


__all__ = [
    "audit_deployment_frontier_closure_graph",
    "build_deployment_frontier_closure_graph",
]
